import typing
from collections.abc import AsyncIterator
from collections.abc import Mapping
from collections.abc import Sequence

from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import StreamingResponse

from core.api.api_request import KibaApiRequest
from core.api.api_response import KibaJSONResponse
from core.api.json_route import json_route
from core.api.rate_limit import rate_limit
from core.api.route_metadata import RateLimitConfig
from core.api.route_metadata import RouteMetadata
from core.api.route_metadata import update_route_metadata
from core.api.streaming_json_route import streaming_json_route

_AnyReturn = typing.Awaitable[typing.Any] | AsyncIterator[typing.Any]  # type: ignore[explicit-any]
_Handler = typing.Callable[[KibaApiRequest[typing.Any]], _AnyReturn]  # type: ignore[explicit-any]
_AuthDecorator = typing.Callable[[_Handler], _Handler]  # type: ignore[explicit-any]


def route[ApiRequest: BaseModel, ApiResponse: BaseModel](  # type: ignore[explicit-any]
    requestType: typing.Type[ApiRequest],
    responseType: typing.Type[ApiResponse],
    *,
    isStreaming: bool = False,
    operationId: str | None = None,
    summary: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    auth: Sequence[_AuthDecorator] = (),
    rateLimit: RateLimitConfig | None = None,
    extensions: Mapping[str, object] | None = None,
) -> typing.Callable[[typing.Callable[[KibaApiRequest[ApiRequest]], _AnyReturn]], typing.Callable[[Request], typing.Awaitable[KibaJSONResponse | StreamingResponse]]]:
    def decorator(func: typing.Callable[[KibaApiRequest[ApiRequest]], _AnyReturn]) -> typing.Callable[[Request], typing.Awaitable[KibaJSONResponse | StreamingResponse]]:  # type: ignore[explicit-any]
        handler: typing.Callable[[KibaApiRequest[ApiRequest]], _AnyReturn] = func
        if rateLimit is not None:
            handler = rate_limit(rateLimit)(handler)
        for authDecorator in reversed(auth):
            handler = authDecorator(handler)  # type: ignore[assignment]
        endpointDecorator = streaming_json_route if isStreaming else json_route
        endpoint = endpointDecorator(requestType=requestType, responseType=responseType)(handler)  # type: ignore[arg-type, ty:invalid-argument-type]
        metadata: RouteMetadata = {
            'requestType': requestType,
            'responseType': responseType,
            'streamed': isStreaming,
            'operationId': operationId,
            'summary': summary,
            'description': description,
            'tags': tags or [],
            'extensions': dict(extensions) if extensions else {},
        }
        update_route_metadata(endpoint, metadata)
        return endpoint

    return decorator
