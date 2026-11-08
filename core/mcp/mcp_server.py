import base64
import binascii
import typing
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence

from pydantic import BaseModel
from pydantic import JsonValue
from pydantic import ValidationError

from core import logging
from core.exceptions import ClientException
from core.mcp.model import McpHttpResponse
from core.mcp.model import McpRequest
from core.mcp.model import McpToolCall
from core.mcp.model import McpUser
from core.util import json_util
from core.util.typing_util import JsonObject

MODERN_PROTOCOL_VERSIONS = ('2026-07-28',)
# NOTE(krishan711): 2024-11-05 used the old HTTP+SSE transport, so it can't reach this streamable HTTP endpoint
LEGACY_PROTOCOL_VERSIONS = ('2025-11-25', '2025-06-18', '2025-03-26')
SUPPORTED_PROTOCOL_VERSIONS = MODERN_PROTOCOL_VERSIONS + LEGACY_PROTOCOL_VERSIONS
PROTOCOL_VERSION_META_KEY = 'io.modelcontextprotocol/protocolVersion'
CLIENT_CAPABILITIES_META_KEY = 'io.modelcontextprotocol/clientCapabilities'
SERVER_INFO_META_KEY = 'io.modelcontextprotocol/serverInfo'
PARSE_ERROR_CODE = -32700
INVALID_REQUEST_ERROR_CODE = -32600
METHOD_NOT_FOUND_ERROR_CODE = -32601
INVALID_PARAMS_ERROR_CODE = -32602
HEADER_MISMATCH_ERROR_CODE = -32020
UNSUPPORTED_PROTOCOL_VERSION_ERROR_CODE = -32022
BASE64_HEADER_PREFIX = '=?base64?'
BASE64_HEADER_SUFFIX = '?='

type McpToolResult = str | BaseModel
type McpToolCaller = Callable[[dict[str, JsonValue], McpUser], Awaitable[McpToolResult]]


class McpServer:
    def __init__(self, name: str, version: str, instructions: str | None = None, listTtlMs: int = 300_000) -> None:
        self.name = name
        self.version = version
        self.instructions = instructions
        self.listTtlMs = listTtlMs
        self._toolDefinitions: list[JsonObject] = []
        self._toolCallers: dict[str, McpToolCaller] = {}

    def register_tool[ArgumentsT: BaseModel](
        self,
        name: str,
        title: str,
        description: str,
        argumentsType: type[ArgumentsT],
        handler: Callable[[ArgumentsT, McpUser], Awaitable[McpToolResult]],
        outputType: type[BaseModel] | None = None,
        isReadOnly: bool = False,
    ) -> None:
        if name in self._toolCallers:
            raise ValueError(f'Tool {name} is already registered')

        async def call_tool(arguments: dict[str, JsonValue], user: McpUser) -> McpToolResult:
            return await handler(argumentsType.model_validate(arguments), user)

        toolDefinition: JsonObject = {
            'name': name,
            'title': title,
            'description': description,
            'inputSchema': typing.cast(JsonObject, argumentsType.model_json_schema()),
            'annotations': {'readOnlyHint': isReadOnly, 'destructiveHint': not isReadOnly},
        }
        if outputType is not None:
            toolDefinition['outputSchema'] = typing.cast(JsonObject, outputType.model_json_schema(mode='serialization'))
        self._toolCallers[name] = call_tool
        self._toolDefinitions.append(toolDefinition)

    async def handle_http_message(self, body: bytes, headers: Mapping[str, str], user: McpUser) -> McpHttpResponse:
        try:
            message = json_util.loads(body)
        except json_util.JsonDecodeException:
            return self._error_response(statusCode=400, requestId=None, code=PARSE_ERROR_CODE, message='Parse error')
        if isinstance(message, list):
            return await self._handle_legacy_batch(messages=message, headers=headers, user=user)
        try:
            request = McpRequest.model_validate(message)
        except ValidationError:
            return self._error_response(statusCode=400, requestId=None, code=INVALID_REQUEST_ERROR_CODE, message='Invalid request')
        meta = request.params.get('_meta')
        protocolVersion = meta.get(PROTOCOL_VERSION_META_KEY) if isinstance(meta, dict) else None
        if protocolVersion is not None:
            return await self._handle_modern_request(request=request, protocolVersion=protocolVersion, headers=headers, user=user)
        return await self._handle_legacy_request(request=request, headers=headers, user=user)

    async def _handle_modern_request(self, request: McpRequest, protocolVersion: JsonValue, headers: Mapping[str, str], user: McpUser) -> McpHttpResponse:
        if not isinstance(protocolVersion, str) or protocolVersion not in MODERN_PROTOCOL_VERSIONS:
            return self._error_response(
                statusCode=400,
                requestId=request.id,
                code=UNSUPPORTED_PROTOCOL_VERSION_ERROR_CODE,
                message='Unsupported protocol version',
                data={'supported': list(SUPPORTED_PROTOCOL_VERSIONS), 'requested': protocolVersion},
            )
        headerMismatch = self._get_header_mismatch(request=request, protocolVersion=protocolVersion, headers=headers)
        if headerMismatch is not None:
            return self._error_response(statusCode=400, requestId=request.id, code=HEADER_MISMATCH_ERROR_CODE, message=f'Header mismatch: {headerMismatch}')
        if request.id is None:
            return McpHttpResponse(statusCode=202)
        meta = typing.cast(dict[str, JsonValue], request.params['_meta'])
        if not isinstance(meta.get(CLIENT_CAPABILITIES_META_KEY), dict):
            return self._error_response(statusCode=400, requestId=request.id, code=INVALID_PARAMS_ERROR_CODE, message=f'Missing _meta {CLIENT_CAPABILITIES_META_KEY}')
        result: JsonObject
        if request.method == 'server/discover':
            result = {'supportedVersions': list(SUPPORTED_PROTOCOL_VERSIONS), 'capabilities': {'tools': {}}, **self._instructions_field(), 'ttlMs': self.listTtlMs, 'cacheScope': 'public'}
        elif request.method == 'tools/list':
            result = {'tools': typing.cast(list[JsonValue], self._toolDefinitions), 'ttlMs': self.listTtlMs, 'cacheScope': 'public'}
        elif request.method == 'tools/call':
            toolResult = await self._call_tool_request(request=request, user=user)
            if isinstance(toolResult, McpHttpResponse):
                return toolResult
            result = toolResult
        else:
            return self._error_response(statusCode=404, requestId=request.id, code=METHOD_NOT_FOUND_ERROR_CODE, message=f'Method not found: {request.method}')
        result = {**result, 'resultType': 'complete', '_meta': {SERVER_INFO_META_KEY: self._server_info()}}
        return McpHttpResponse(statusCode=200, body={'jsonrpc': '2.0', 'id': request.id, 'result': result})

    async def _handle_legacy_batch(self, messages: Sequence[object], headers: Mapping[str, str], user: McpUser) -> McpHttpResponse:
        if not messages:
            return self._error_response(statusCode=400, requestId=None, code=INVALID_REQUEST_ERROR_CODE, message='Invalid request: empty batch')
        responses: list[JsonValue] = []
        for message in messages:
            try:
                request = McpRequest.model_validate(message)
            except ValidationError:
                responses.append(typing.cast(JsonValue, self._error_body(requestId=None, code=INVALID_REQUEST_ERROR_CODE, message='Invalid request')))
                continue
            response = await self._handle_legacy_request(request=request, headers=headers, user=user)
            if response.body is not None:
                responses.append(response.body)
        return McpHttpResponse(statusCode=200, body=responses) if responses else McpHttpResponse(statusCode=202)

    async def _handle_legacy_request(self, request: McpRequest, headers: Mapping[str, str], user: McpUser) -> McpHttpResponse:
        headerProtocolVersion = _get_header(headers=headers, name='MCP-Protocol-Version')
        if headerProtocolVersion is not None and headerProtocolVersion not in LEGACY_PROTOCOL_VERSIONS and request.method != 'initialize':
            return self._error_response(statusCode=400, requestId=request.id, code=INVALID_REQUEST_ERROR_CODE, message=f'Unsupported protocol version: {headerProtocolVersion}. Supported without _meta: {", ".join(LEGACY_PROTOCOL_VERSIONS)}')
        if request.id is None:
            return McpHttpResponse(statusCode=202)
        result: JsonObject
        if request.method == 'initialize':
            requestedProtocolVersion = request.params.get('protocolVersion')
            protocolVersion = requestedProtocolVersion if isinstance(requestedProtocolVersion, str) and requestedProtocolVersion in LEGACY_PROTOCOL_VERSIONS else LEGACY_PROTOCOL_VERSIONS[0]
            result = {'protocolVersion': protocolVersion, 'capabilities': {'tools': {}}, 'serverInfo': self._server_info(), **self._instructions_field()}
        elif request.method == 'ping':
            result = {}
        elif request.method == 'tools/list':
            result = {'tools': typing.cast(list[JsonValue], self._toolDefinitions)}
        elif request.method == 'tools/call':
            toolResult = await self._call_tool_request(request=request, user=user)
            if isinstance(toolResult, McpHttpResponse):
                return toolResult
            result = toolResult
        else:
            return self._error_response(statusCode=200, requestId=request.id, code=METHOD_NOT_FOUND_ERROR_CODE, message=f'Method not found: {request.method}')
        return McpHttpResponse(statusCode=200, body={'jsonrpc': '2.0', 'id': request.id, 'result': result})

    async def _call_tool_request(self, request: McpRequest, user: McpUser) -> JsonObject | McpHttpResponse:
        try:
            toolCall = McpToolCall.model_validate({key: value for key, value in request.params.items() if key != '_meta'})
        except ValidationError as exception:
            return self._error_response(statusCode=400, requestId=request.id, code=INVALID_PARAMS_ERROR_CODE, message=str(exception))
        logging.info(f'MCP tool call {toolCall.name} by {user.userId}')
        toolCaller = self._toolCallers.get(toolCall.name)
        if toolCaller is None:
            return self._tool_result(text=f'Unknown tool: {toolCall.name}', isError=True)
        try:
            toolResult = await toolCaller(toolCall.arguments, user)
        except ValidationError as exception:
            return self._tool_result(text=f'Invalid arguments: {exception}', isError=True)
        except ClientException as exception:
            return self._tool_result(text=exception.message or exception.exceptionType, isError=True)
        if isinstance(toolResult, BaseModel):
            structuredContent = typing.cast(JsonObject, toolResult.model_dump(mode='json', by_alias=True))
            return {**self._tool_result(text=json_util.dumps(structuredContent), isError=False), 'structuredContent': structuredContent}
        return self._tool_result(text=toolResult, isError=False)

    @staticmethod
    def _get_header_mismatch(request: McpRequest, protocolVersion: str, headers: Mapping[str, str]) -> str | None:
        headerProtocolVersion = _get_header(headers=headers, name='MCP-Protocol-Version')
        if headerProtocolVersion != protocolVersion:
            return f'MCP-Protocol-Version header value {headerProtocolVersion!r} does not match body value {protocolVersion!r}'
        headerMethod = _get_header(headers=headers, name='Mcp-Method')
        if headerMethod != request.method:
            return f'Mcp-Method header value {headerMethod!r} does not match body value {request.method!r}'
        if request.method == 'tools/call':
            headerName = _decode_header_value(value=_get_header(headers=headers, name='Mcp-Name'))
            bodyName = request.params.get('name')
            if headerName is None or headerName != bodyName:
                return f'Mcp-Name header value {headerName!r} does not match body value {bodyName!r}'
        return None

    def _server_info(self) -> JsonObject:
        return {'name': self.name, 'version': self.version}

    def _instructions_field(self) -> JsonObject:
        return {'instructions': self.instructions} if self.instructions else {}

    @staticmethod
    def _tool_result(text: str, isError: bool) -> JsonObject:
        return {'content': [{'type': 'text', 'text': text}], 'isError': isError}

    @staticmethod
    def _error_body(requestId: int | str | None, code: int, message: str, data: JsonObject | None = None) -> JsonObject:
        error: JsonObject = {'code': code, 'message': message}
        if data is not None:
            error['data'] = data
        return {'jsonrpc': '2.0', 'id': requestId, 'error': error}

    @staticmethod
    def _error_response(statusCode: int, requestId: int | str | None, code: int, message: str, data: JsonObject | None = None) -> McpHttpResponse:
        return McpHttpResponse(statusCode=statusCode, body=McpServer._error_body(requestId=requestId, code=code, message=message, data=data))


def _get_header(headers: Mapping[str, str], name: str) -> str | None:
    lowerName = name.lower()
    return next((value for key, value in headers.items() if key.lower() == lowerName), None)


def _decode_header_value(value: str | None) -> str | None:
    if value is None or not (value.startswith(BASE64_HEADER_PREFIX) and value.endswith(BASE64_HEADER_SUFFIX)):
        return value
    try:
        return base64.b64decode(value[len(BASE64_HEADER_PREFIX) : -len(BASE64_HEADER_SUFFIX)], validate=True).decode('utf-8')
    except (binascii.Error, UnicodeDecodeError):
        return None
