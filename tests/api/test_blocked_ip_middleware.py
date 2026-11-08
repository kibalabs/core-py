import http
import typing
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.types import Message
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from core.api.middleware.blocked_ip_middleware import BlockedIpMiddleware
from core.api.middleware.blocked_ip_middleware import TorExitList
from core.requester import Requester

BLOCKED_NETWORKS = ['64.118.151.0/24', '65.109.215.187/32']
TRUSTED_PROXY_HEADERS = ['X-Forwarded-For', 'X-Real-IP']


def _tor_exit_list(listText: str) -> TorExitList:
    requester = typing.cast(Requester, SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(text=listText))))
    return TorExitList(requester=requester)


async def _run(headers: list[tuple[bytes, bytes]], clientIp: str = '10.0.0.1', torExitList: TorExitList | None = None, trustedProxyHeaders: list[str] = TRUSTED_PROXY_HEADERS) -> http.HTTPStatus:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})

    async def receive() -> Message:
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    sentMessages: list[Message] = []

    async def send(message: Message) -> None:
        sentMessages.append(message)

    scope: Scope = {'type': 'http', 'method': 'GET', 'path': '/health', 'headers': headers, 'client': (clientIp, 1234), 'query_string': b''}
    middleware = BlockedIpMiddleware(app=app, blockedNetworks=BLOCKED_NETWORKS, torExitList=torExitList, trustedProxyHeaders=trustedProxyHeaders)
    await middleware(scope, receive, send)
    return http.HTTPStatus(sentMessages[0]['status'])


@pytest.mark.asyncio
async def test_blocks_ip_in_range_from_proxy_header() -> None:
    assert await _run(headers=[(b'x-forwarded-for', b'64.118.151.183')]) == http.HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_blocks_when_client_prepends_a_spoofed_forwarded_for_hop() -> None:
    assert await _run(headers=[(b'x-forwarded-for', b'1.2.3.4, 64.118.151.181')]) == http.HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_blocks_direct_client_ip() -> None:
    assert await _run(headers=[], clientIp='64.118.151.10') == http.HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_blocks_single_address_network() -> None:
    assert await _run(headers=[(b'x-forwarded-for', b'65.109.215.187')]) == http.HTTPStatus.FORBIDDEN
    assert await _run(headers=[(b'x-forwarded-for', b'65.109.215.188')]) == http.HTTPStatus.OK


@pytest.mark.asyncio
async def test_allows_ip_outside_range_and_ignores_unparseable_values() -> None:
    assert await _run(headers=[(b'x-forwarded-for', b'64.118.152.1'), (b'x-real-ip', b'not-an-ip')]) == http.HTTPStatus.OK


@pytest.mark.asyncio
async def test_ignores_headers_that_are_not_trusted() -> None:
    assert await _run(headers=[(b'x-forwarded-for', b'64.118.151.183')], trustedProxyHeaders=[]) == http.HTTPStatus.OK


@pytest.mark.asyncio
async def test_blocks_tor_exit_after_load() -> None:
    torExitList = _tor_exit_list(listText='109.70.100.9\n192.42.116.45\n2001:db8::1\n')
    await torExitList.load()
    assert await _run(headers=[(b'x-real-ip', b'109.70.100.9')], torExitList=torExitList) == http.HTTPStatus.FORBIDDEN
    assert await _run(headers=[(b'x-forwarded-for', b'2001:db8::1')], torExitList=torExitList) == http.HTTPStatus.FORBIDDEN
    assert await _run(headers=[(b'x-real-ip', b'109.70.100.10')], torExitList=torExitList) == http.HTTPStatus.OK


@pytest.mark.asyncio
async def test_failed_tor_load_does_not_raise_or_block() -> None:
    requester = typing.cast(Requester, SimpleNamespace(get=AsyncMock(side_effect=TimeoutError('timed out'))))
    torExitList = TorExitList(requester=requester)
    await torExitList.load()
    assert await _run(headers=[(b'x-real-ip', b'109.70.100.9')], torExitList=torExitList) == http.HTTPStatus.OK
