import time
import typing
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match
from starlette.routing import Router
from starlette.types import ASGIApp
from starlette.types import Scope

from core import logging
from core.util.value_holder import RequestIdHolder


def _find_path_pattern(scope: Scope, prefix: str = '') -> str | None:
    routes = scope['endpoint'].routes if 'endpoint' in scope else scope['app'].routes
    for route in routes:
        match_state, match_scope = route.matches(scope)
        if match_state != Match.NONE:
            if isinstance(match_scope['endpoint'], Router):
                return _find_path_pattern(
                    scope={**match_scope, 'type': scope['type'], 'path': scope['path'][len(match_scope['root_path']) :], 'method': scope['method']},
                    prefix=prefix + match_scope['root_path'],
                )
            return prefix + typing.cast(str, route.path)
    return None


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, requestIdHolder: RequestIdHolder | None = None) -> None:
        super().__init__(app=app)
        self.requestIdHolder = requestIdHolder

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        requestId = str(uuid.uuid4()).replace('-', '')
        if self.requestIdHolder:
            self.requestIdHolder.set_value(value=requestId)
        startTime = time.time()
        pathPattern = _find_path_pattern(request.scope) or request.url.path
        logging.api(action=request.method, path=request.url.path, pathPattern=pathPattern, query=request.url.query)
        response = await call_next(request)
        duration = time.time() - startTime
        response.headers['X-Response-Time'] = str(duration)
        response.headers['X-Request-Id'] = requestId
        logging.api(action=request.method, path=request.url.path, pathPattern=pathPattern, query=request.url.query, response=response.status_code, duration=duration)
        if self.requestIdHolder:
            self.requestIdHolder.set_value(value=None)
        return response
