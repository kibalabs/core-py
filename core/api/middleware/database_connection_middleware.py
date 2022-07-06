from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from core.store.database import Database


class DatabaseConnectionMiddleware(BaseHTTPMiddleware):

    def __init__(self, app: ASGIApp, database: Database) -> None:
        super().__init__(app=app)
        self.database = database

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in {'GET', 'OPTIONS', 'HEAD'}:
            response = await call_next(request)
        else:
            async with self.database.create_context_connection():
                response = await call_next(request)
        return response
