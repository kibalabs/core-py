import functools
import typing
from collections.abc import Mapping

from pydantic import BaseModel
from pydantic import ValidationError
from starlette.requests import Request

from core.api.api_request import KibaApiRequest
from core.api.api_response import KibaJSONResponse
from core.api.route_metadata import OpenApiSecurity
from core.api.route_metadata import RateLimitConfig
from core.api.route_metadata import RouteMetadata
from core.api.route_metadata import update_route_metadata
from core.exceptions import BadRequestException
from core.exceptions import InternalServerErrorException
from core.util import json_util
from core.util.typing_util import JsonObject


def json_route[ApiRequest: BaseModel, ApiResponse: BaseModel](
    requestType: typing.Type[ApiRequest],
    responseType: typing.Type[ApiResponse],
    *,
    documented: bool = False,
    operationId: str | None = None,
    summary: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    security: OpenApiSecurity | None = None,
    rateLimit: RateLimitConfig | None = None,
    extensions: Mapping[str, object] | None = None,
) -> typing.Callable[[typing.Callable[[KibaApiRequest[ApiRequest]], typing.Awaitable[ApiResponse]]], typing.Callable[[Request], typing.Awaitable[KibaJSONResponse]]]:
    def decorator(func: typing.Callable[[KibaApiRequest[ApiRequest]], typing.Awaitable[ApiResponse]]) -> typing.Callable[[Request], typing.Awaitable[KibaJSONResponse]]:
        endpoint = _json_route(requestType=requestType, responseType=responseType)(func)
        metadata: RouteMetadata = {
            'requestType': requestType,
            'responseType': responseType,
            'streamed': False,
            'documented': documented,
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


def _json_route[ApiRequest: BaseModel, ApiResponse: BaseModel](
    requestType: typing.Type[ApiRequest],
    responseType: typing.Type[ApiResponse],
) -> typing.Callable[[typing.Callable[[KibaApiRequest[ApiRequest]], typing.Awaitable[ApiResponse]]], typing.Callable[[Request], typing.Awaitable[KibaJSONResponse]]]:
    def decorator(func: typing.Callable[[KibaApiRequest[ApiRequest]], typing.Awaitable[ApiResponse]]) -> typing.Callable[[Request], typing.Awaitable[KibaJSONResponse]]:
        @functools.wraps(func)
        async def async_wrapper(receivedRequest: Request) -> KibaJSONResponse:
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
            kibaRequest.data = requestParams
            receivedResponse = await func(kibaRequest)
            if not isinstance(receivedResponse, responseType):
                raise InternalServerErrorException(f'Expected response to be of type {responseType}, got {type(receivedResponse)}')
            return KibaJSONResponse(content=receivedResponse.model_dump())

        return async_wrapper

    return decorator
