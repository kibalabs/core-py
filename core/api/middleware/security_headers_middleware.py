from collections.abc import Mapping

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp
from starlette.types import Message
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, headers: Mapping[str, str]) -> None:
        self.app = app
        self.headers = dict(headers)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message['type'] == 'http.response.start':
                MutableHeaders(scope=message).update(self.headers)
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
