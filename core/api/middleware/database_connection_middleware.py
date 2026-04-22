from starlette.types import ASGIApp
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from core.store.database import Database


class DatabaseConnectionMiddleware:
    def __init__(self, app: ASGIApp, database: Database) -> None:
        self.app = app
        self.database = database

    # NOTE(krishan711): see note in database.py about why this can cause problems with concurrent operations
    # NOTE(krishan711): raw ASGI (not BaseHTTPMiddleware) so the DB connection stays open across streaming body
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        async with self.database.create_context_connection():
            await self.app(scope, receive, send)
