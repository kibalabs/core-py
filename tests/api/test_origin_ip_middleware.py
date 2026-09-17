from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from core.api.api_request import KibaApiRequest
from core.api.json_route import json_route
from core.api.middleware.origin_ip_middleware import OriginIpMiddleware


class ExampleRequest(BaseModel):
    value: str


class ExampleResponse(BaseModel):
    originIp: str | None


def _build_client(*, trustedProxyHeaders: tuple[str, ...] = ()) -> TestClient:
    @json_route(requestType=ExampleRequest, responseType=ExampleResponse)
    async def echo_origin_ip(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(originIp=request.originIp)

    app = Starlette(routes=[Route('/echo', echo_origin_ip, methods=['POST'])])
    app.add_middleware(OriginIpMiddleware, trustedProxyHeaders=list(trustedProxyHeaders))
    return TestClient(app)


def test_origin_ip_middleware_defaults_to_socket_peer() -> None:
    client = _build_client()
    response = client.post('/echo', json={'value': 'x'}, headers={'X-Forwarded-For': '9.9.9.9'})
    assert response.status_code == 200
    assert response.json()['originIp'] == 'testclient'


def test_origin_ip_middleware_trusts_configured_header() -> None:
    client = _build_client(trustedProxyHeaders=('X-Forwarded-For',))
    response = client.post('/echo', json={'value': 'x'}, headers={'X-Forwarded-For': '9.9.9.9, 10.0.0.1'})
    assert response.status_code == 200
    assert response.json()['originIp'] == '9.9.9.9'


def test_origin_ip_middleware_falls_back_when_header_absent() -> None:
    client = _build_client(trustedProxyHeaders=('X-Forwarded-For',))
    response = client.post('/echo', json={'value': 'x'})
    assert response.status_code == 200
    assert response.json()['originIp'] == 'testclient'


def test_origin_ip_middleware_checks_headers_in_order() -> None:
    client = _build_client(trustedProxyHeaders=('X-Forwarded-For', 'X-Real-IP'))
    response = client.post('/echo', json={'value': 'x'}, headers={'X-Real-IP': '7.7.7.7'})
    assert response.status_code == 200
    assert response.json()['originIp'] == '7.7.7.7'
