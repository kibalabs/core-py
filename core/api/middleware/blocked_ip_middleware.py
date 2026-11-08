import ipaddress
from collections.abc import Collection

from starlette.datastructures import Headers
from starlette.responses import Response
from starlette.types import ASGIApp
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from core import logging
from core.requester import Requester

IpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

TOR_EXIT_LIST_URL = 'https://check.torproject.org/torbulkexitlist'


def _parse_ip(value: str) -> IpAddress | None:
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


class TorExitList:
    def __init__(self, requester: Requester) -> None:
        self.requester = requester
        self.addresses: frozenset[IpAddress] = frozenset()

    async def load(self) -> None:
        try:
            response = await self.requester.get(url=TOR_EXIT_LIST_URL, timeout=30)
        except Exception as exception:  # noqa: BLE001
            logging.error(f'Failed to load Tor exit list, Tor exits will not be blocked: {exception}')
            return
        self.addresses = frozenset(address for address in (_parse_ip(value=line) for line in response.text.splitlines()) if address is not None)
        logging.info(f'Loaded {len(self.addresses)} Tor exit addresses')


class BlockedIpMiddleware:
    def __init__(self, app: ASGIApp, blockedNetworks: Collection[str] = (), torExitList: TorExitList | None = None, trustedProxyHeaders: Collection[str] = ()) -> None:
        self.app = app
        self.blockedNetworks = [ipaddress.ip_network(network) for network in blockedNetworks]
        self.torExitList = torExitList
        self.trustedProxyHeaders = tuple(trustedProxyHeaders)

    def _is_blocked_ip(self, value: str) -> bool:
        address = _parse_ip(value=value)
        if address is None:
            return False
        if self.torExitList is not None and address in self.torExitList.addresses:
            return True
        return any(address in network for network in self.blockedNetworks)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        # NOTE(krishan711): every hop in the proxy headers is checked (not just the first like OriginIpMiddleware) so a spoofed first hop can't hide a blocked address
        candidateIps = [value for headerName in self.trustedProxyHeaders for value in headers.get(headerName, '').split(',')]
        client = scope.get('client')
        if client:
            candidateIps.append(str(client[0]))
        if any(self._is_blocked_ip(value=candidateIp) for candidateIp in candidateIps):
            await Response(status_code=403)(scope, receive, send)
            return
        await self.app(scope, receive, send)
