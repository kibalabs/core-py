from collections.abc import Collection

from starlette.datastructures import MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp
from starlette.types import Message
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send


# NOTE(krishan711): add this after starlette's CORSMiddleware so it runs outside it, otherwise CORSMiddleware rejects
# preflights for these paths from origins it doesn't allow before they get here
class PublicCorsMiddleware:
    def __init__(self, app: ASGIApp, paths: Collection[str], allowedMethods: Collection[str] = ('GET',)) -> None:
        self.app = app
        self.paths = frozenset(paths)
        self.allowMethodsHeader = ', '.join([*allowedMethods, 'OPTIONS'])

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http' or scope['path'] not in self.paths:
            await self.app(scope, receive, send)
            return
        if scope['method'] == 'OPTIONS':
            response = Response(
                status_code=204,
                headers={
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': self.allowMethodsHeader,
                    'Access-Control-Allow-Headers': '*',
                },
            )
            await response(scope, receive, send)
            return

        async def send_with_cors_header(message: Message) -> None:
            if message['type'] == 'http.response.start':
                MutableHeaders(scope=message).setdefault('Access-Control-Allow-Origin', '*')
            await send(message)

        await self.app(scope, receive, send_with_cors_header)
