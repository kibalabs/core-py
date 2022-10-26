import time
import uuid
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from core import logging
from core.util.value_holder import RequestIdHolder


class LoggingMiddleware(BaseHTTPMiddleware):

    def __init__(self, app: ASGIApp, requestIdHolder: Optional[RequestIdHolder] = None):
        super().__init__(app=app)
        self.requestIdHolder = requestIdHolder

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        requestId = str(uuid.uuid4()).replace('-', '')
        if self.requestIdHolder:
            self.requestIdHolder.set_value(value=requestId)
        startTime = time.time()
        logging.api(action=request.method, path=request.url.path, query=request.url.query)
        response = await call_next(request)
        duration = time.time() - startTime
        response.headers['X-Response-Time'] = str(duration)
        response.headers['X-Request-Id'] = requestId
        logging.api(action=request.method, path=request.url.path, query=request.url.query, response=response.status_code, duration=duration)
        if self.requestIdHolder:
            self.requestIdHolder.set_value(value=None)
        return response
