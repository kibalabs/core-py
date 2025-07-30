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

    # NOTE(krishan711): see note in database.py about why this can cause problems with concurrent operations
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # NOTE(krishan711): hack to prevent running this for streaming endpoints because streaming
        # endpoints return a response with a generator inside it so this middleware wouldn't work
        if request.scope['path'].endswith('-streamed'):
            return await call_next(request)
        # isReadonly = request.method in {'GET', 'OPTIONS', 'HEAD'}
        async with self.database.create_context_connection():
            response = await call_next(request)
        return response
