from starlette.types import ASGIApp
from starlette.types import Message
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

            # NOTE(krishan711): commit before the response starts, otherwise a client can get the response and make its
            # next request before this request's writes are visible. Anything after this (e.g. while streaming) is
            # committed when the context connection ends
            async def send_after_commit(message: Message) -> None:
                if message['type'] == 'http.response.start':
                    await self.database.commit_context_connection()
                await send(message)

            await self.app(scope, receive, send_after_commit)
