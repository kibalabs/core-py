import functools
import inspect
import typing
from collections.abc import AsyncIterator
from collections.abc import Mapping

from pydantic import BaseModel
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import StreamingResponse

from core.api.api_request import KibaApiRequest
from core.api.route_metadata import OpenApiSecurity
from core.api.route_metadata import RateLimitConfig
from core.api.route_metadata import RouteMetadata
from core.api.route_metadata import update_route_metadata
from core.exceptions import BadRequestException
from core.exceptions import InternalServerErrorException
from core.util import json_util
from core.util.typing_util import JsonObject


async def _convert_to_json_generator[T: BaseModel](response_iterator: AsyncIterator[T], expectedType: typing.Type[T]) -> AsyncIterator[bytes]:
    async for content in response_iterator:
        if not isinstance(content, expectedType):
            raise InternalServerErrorException(f'Expected response to be of type {expectedType}, got {type(content)}')
        yield json_util.dumpb(content.model_dump()) + b'\n'


def streaming_json_route[ApiRequest: BaseModel, ApiResponse: BaseModel](
    requestType: typing.Type[ApiRequest],
    responseType: typing.Type[ApiResponse],
    *,
    operationId: str | None = None,
    summary: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    security: OpenApiSecurity | None = None,
    rateLimit: RateLimitConfig | None = None,
    extensions: Mapping[str, object] | None = None,
) -> typing.Callable[[typing.Callable[[KibaApiRequest[ApiRequest]], AsyncIterator[ApiResponse]]], typing.Callable[[Request], typing.Awaitable[StreamingResponse]]]:
    def decorator(func: typing.Callable[[KibaApiRequest[ApiRequest]], AsyncIterator[ApiResponse]]) -> typing.Callable[[Request], typing.Awaitable[StreamingResponse]]:
        endpoint = _streaming_json_route(requestType=requestType, responseType=responseType)(func)
        metadata: RouteMetadata = {
            'requestType': requestType,
            'responseType': responseType,
            'streamed': True,
            'operationId': operationId,
            'summary': summary,
            'description': description,
            'tags': tags or [],
        }
        if security is not None:
            metadata['security'] = security
        if rateLimit is not None:
            metadata['rateLimit'] = rateLimit
        if extensions is not None:
            metadata['extensions'] = dict(extensions)
        update_route_metadata(endpoint, metadata)
        return endpoint

    return decorator


def _streaming_json_route[ApiRequest: BaseModel, ApiResponse: BaseModel](
    requestType: typing.Type[ApiRequest],
    responseType: typing.Type[ApiResponse],
) -> typing.Callable[[typing.Callable[[KibaApiRequest[ApiRequest]], AsyncIterator[ApiResponse]]], typing.Callable[[Request], typing.Awaitable[StreamingResponse]]]:
    def decorator(func: typing.Callable[[KibaApiRequest[ApiRequest]], AsyncIterator[ApiResponse]]) -> typing.Callable[[Request], typing.Awaitable[StreamingResponse]]:
        @functools.wraps(func)
        async def async_wrapper(receivedRequest: Request) -> StreamingResponse:
            pathParams = receivedRequest.path_params
            queryParams = receivedRequest.query_params
            bodyBytes = await receivedRequest.body()
            if len(bodyBytes) == 0:
                body: JsonObject = {}
            else:
                try:
                    body = typing.cast(JsonObject, json_util.loads(bodyBytes.decode()))
                except json_util.JsonDecodeException as exception:
                    raise BadRequestException(f'Invalid JSON body: {exception}')
            allParams = {**pathParams, **body, **queryParams}
            try:
                requestParams = requestType(**allParams)
            except ValidationError as exception:
                validationErrorMessage = ', '.join([f'{".".join([str(value) for value in error["loc"]])}: {error["msg"]}' for error in exception.errors()])
                raise BadRequestException(f'Invalid request: {validationErrorMessage}')
            kibaRequest: KibaApiRequest[ApiRequest] = KibaApiRequest(scope=receivedRequest.scope, receive=receivedRequest._receive, send=receivedRequest._send)  # noqa: SLF001
            kibaRequest.originIp = typing.cast('str | None', receivedRequest.scope.get('originIp'))
            kibaRequest.data = requestParams
            responseGeneratorOrAwaitable = func(kibaRequest)
            responseGenerator = await responseGeneratorOrAwaitable if inspect.isawaitable(responseGeneratorOrAwaitable) else responseGeneratorOrAwaitable
            wrappedGenerator = _convert_to_json_generator(typing.cast(AsyncIterator[BaseModel], responseGenerator), expectedType=typing.cast(typing.Type[BaseModel], responseType))
            # NOTE(krishan711): we set content-encoding to identity to prevent gzip from trying to process it (cos it buffers all the content)
            return StreamingResponse(content=wrappedGenerator, media_type='application/x-ndjson', headers={'Content-Encoding': 'identity'})

        return async_wrapper

    return decorator
