from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class ServerHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, name: str | None = None, version: str | None = None, environment: str | None = None) -> None:
        super().__init__(app=app)
        self.name = name
        self.version = version
        self.environment = environment

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if self.name:
            response.headers['X-Server-Name'] = self.name
        if self.version:
            response.headers['X-Server-Version'] = self.version
        if self.environment:
            response.headers['X-Server-Environment'] = self.environment
        return response
