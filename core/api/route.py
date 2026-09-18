import functools
import typing
from collections.abc import AsyncIterator
from collections.abc import Mapping

from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import StreamingResponse

from core.api.api_request import KibaApiRequest
from core.api.api_response import KibaJSONResponse
from core.api.json_route import json_route
from core.api.rate_limit import rate_limit
from core.api.route_auth import RouteAuthResolver
from core.api.route_metadata import RateLimitConfig
from core.api.route_metadata import RouteMetadata
from core.api.route_metadata import update_route_metadata
from core.api.streaming_json_route import streaming_json_route

_AnyReturn = typing.Awaitable[typing.Any] | AsyncIterator[typing.Any]  # type: ignore[explicit-any]


def _authorize_route[ApiRequest: BaseModel](
    authResolver: RouteAuthResolver,
    auth: str,
) -> typing.Callable[[typing.Callable[[KibaApiRequest[ApiRequest]], _AnyReturn]], typing.Callable[[KibaApiRequest[ApiRequest]], typing.Any]]:
    def decorator(func: typing.Callable[[KibaApiRequest[ApiRequest]], _AnyReturn]) -> typing.Callable[[KibaApiRequest[ApiRequest]], typing.Any]:  # type: ignore[explicit-any]
        @functools.wraps(func)
        async def async_wrapper(request: KibaApiRequest[ApiRequest]) -> typing.Any:  # type: ignore[explicit-any, misc]
            await authResolver.authorize_route(auth=auth, request=request)
            result = func(request)
            if hasattr(result, '__aiter__'):
                return result
            return await result

        return async_wrapper

    return decorator


class RouteBuilder:
    def __init__(self, authResolver: RouteAuthResolver) -> None:
        self.authResolver = authResolver

    def __call__[ApiRequest: BaseModel, ApiResponse: BaseModel](  # type: ignore[explicit-any]
        self,
        requestType: typing.Type[ApiRequest],
        responseType: typing.Type[ApiResponse],
        *,
        isStreaming: bool = False,
        operationId: str | None = None,
        summary: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        auth: str | None = None,
        rateLimit: RateLimitConfig | None = None,
        extensions: Mapping[str, object] | None = None,
    ) -> typing.Callable[[typing.Callable[[KibaApiRequest[ApiRequest]], _AnyReturn]], typing.Callable[[Request], typing.Awaitable[KibaJSONResponse | StreamingResponse]]]:
        securitySchemeNames = self.authResolver.get_route_security_schemes(auth=auth) if auth is not None else []

        def decorator(func: typing.Callable[[KibaApiRequest[ApiRequest]], _AnyReturn]) -> typing.Callable[[Request], typing.Awaitable[KibaJSONResponse | StreamingResponse]]:  # type: ignore[explicit-any]
            handler: typing.Callable[[KibaApiRequest[ApiRequest]], _AnyReturn] = func
            if rateLimit is not None:
                handler = rate_limit(rateLimit)(handler)
            if auth is not None:
                handler = _authorize_route(self.authResolver, auth)(handler)
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
            if securitySchemeNames:
                update_route_metadata(endpoint, {'security': [{name: []} for name in securitySchemeNames]})
            return endpoint

        return decorator


def create_route(*, authResolver: RouteAuthResolver) -> RouteBuilder:
    return RouteBuilder(authResolver=authResolver)
