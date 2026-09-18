from collections.abc import Sequence

from starlette.datastructures import Headers
from starlette.types import ASGIApp
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from core import logging


def _extract_origin_ip(scope: Scope, trustedProxyHeaders: Sequence[str]) -> str | None:
    headers = Headers(scope=scope)
    for headerName in trustedProxyHeaders:
        headerValue = headers.get(headerName)
        if headerValue:
            return headerValue.split(',')[0].strip()
    client = scope.get('client')
    if client:
        return str(client[0])
    return None


class OriginIpMiddleware:
    def __init__(self, app: ASGIApp, trustedProxyHeaders: Sequence[str] = ()) -> None:
        self.app = app
        self.trustedProxyHeaders = trustedProxyHeaders
        if trustedProxyHeaders:
            logging.info(f'OriginIpMiddleware trusting proxy headers for client IP: {", ".join(trustedProxyHeaders)}. This may be spoofable if requests can reach this service directly.')

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        scope['originIp'] = _extract_origin_ip(scope=scope, trustedProxyHeaders=self.trustedProxyHeaders)
        await self.app(scope, receive, send)
