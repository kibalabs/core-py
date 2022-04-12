import time
from typing import Optional
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from core import logging
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request

from core.util.value_holder import RequestIdHolder
import time
import uuid

from core import logging


class LoggingMiddleware(BaseHTTPMiddleware):

    def __init__(self, app: ASGIApp, requestIdHolder: Optional[RequestIdHolder] = None):
        super().__init__(app)
        self.requestIdHolder = requestIdHolder

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        requestId = str(uuid.uuid4()).replace('-', '')
        self.requestIdHolder.set_value(value=requestId)
        startTime = time.time()
        logging.api(action=request.method, path=request.url.path, query=request.url.query)
        response = await call_next(request)
        duration = time.time() - startTime
        response.headers['X-Response-Time'] = str(duration)
        response.headers['X-Request-Id'] = requestId
        logging.api(action=request.method, path=request.url.path, query=request.url.query, response=response.status_code, duration=duration)
        self.requestIdHolder.set_value(value=None)
        return response