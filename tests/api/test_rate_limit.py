import pytest
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from core.api.api_request import KibaApiRequest
from core.api.json_route import json_route
from core.api.middleware.exception_handling_middleware import ExceptionHandlingMiddleware
from core.api.middleware.origin_ip_middleware import OriginIpMiddleware
from core.api.rate_limit import rate_limit
from core.api.route_metadata import get_route_metadata
from core.exceptions import InternalServerErrorException
from core.http.basic_authentication import BasicAuthentication
from core.http.jwt import Jwt


class ExampleRequest(BaseModel):
    value: str


class ExampleResponse(BaseModel):
    result: str


async def _receive() -> dict[str, object]:
    return {'type': 'http.request'}


async def _send(message: dict[str, object]) -> None:
    del message


def _request() -> KibaApiRequest[ExampleRequest]:
    request = KibaApiRequest(scope={'type': 'http', 'headers': []}, receive=_receive, send=_send)
    request.data = ExampleRequest(value='value')
    return request


def test_rate_limit_publishes_metadata_on_the_route() -> None:
    @rate_limit({'perMinute': 3, 'perHour': 30})
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    assert get_route_metadata(endpoint)['rateLimit'] == {'perMinute': 3, 'perHour': 30}


def test_rate_limit_publishes_key_by_as_part_of_metadata() -> None:
    @rate_limit({'perMinute': 3, 'keyBy': 'ip'})
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    assert get_route_metadata(endpoint)['rateLimit'] == {'perMinute': 3, 'keyBy': 'ip'}


@pytest.mark.asyncio
async def test_rate_limit_user_key_uses_auth_basic_username() -> None:
    @rate_limit({'perMinute': 1})
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    firstRequest = _request()
    firstRequest.authBasic = BasicAuthentication(username='user-1', password='sig')
    secondRequest = _request()
    secondRequest.authBasic = BasicAuthentication(username='user-1', password='sig')
    otherUserRequest = _request()
    otherUserRequest.authBasic = BasicAuthentication(username='user-2', password='sig')

    assert (await endpoint(firstRequest)).result == 'value'
    with pytest.raises(Exception, match='RATE_LIMITED'):
        await endpoint(secondRequest)
    assert (await endpoint(otherUserRequest)).result == 'value'


@pytest.mark.asyncio
async def test_rate_limit_user_key_falls_back_to_auth_jwt_subject() -> None:
    @rate_limit({'perMinute': 1})
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    firstRequest = _request()
    firstRequest.authJwt = Jwt(payloadDict={'sub': 'jwt-user-1'})
    secondRequest = _request()
    secondRequest.authJwt = Jwt(payloadDict={'sub': 'jwt-user-1'})

    assert (await endpoint(firstRequest)).result == 'value'
    with pytest.raises(Exception, match='RATE_LIMITED'):
        await endpoint(secondRequest)


@pytest.mark.asyncio
async def test_rate_limit_user_key_without_auth_raises_internal_error() -> None:
    @rate_limit({'perMinute': 1})
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    with pytest.raises(InternalServerErrorException, match='auth decorator'):
        await endpoint(_request())


@pytest.mark.asyncio
async def test_rate_limit_ip_key_uses_origin_ip() -> None:
    @rate_limit({'perMinute': 1, 'keyBy': 'ip'})
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    firstRequest = _request()
    firstRequest.originIp = '1.2.3.4'
    secondRequest = _request()
    secondRequest.originIp = '1.2.3.4'
    otherIpRequest = _request()
    otherIpRequest.originIp = '5.6.7.8'

    assert (await endpoint(firstRequest)).result == 'value'
    with pytest.raises(Exception, match='RATE_LIMITED'):
        await endpoint(secondRequest)
    assert (await endpoint(otherIpRequest)).result == 'value'


@pytest.mark.asyncio
async def test_rate_limit_ip_key_without_origin_ip_raises_internal_error() -> None:
    @rate_limit({'perMinute': 1, 'keyBy': 'ip'})
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    with pytest.raises(InternalServerErrorException, match='OriginIpMiddleware'):
        await endpoint(_request())


def test_rate_limit_ip_key_through_origin_ip_middleware_trusts_configured_header() -> None:
    @json_route(requestType=ExampleRequest, responseType=ExampleResponse)
    @rate_limit({'perMinute': 1, 'keyBy': 'ip'})
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    app = Starlette(routes=[Route('/limited', endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    app.add_middleware(OriginIpMiddleware, trustedProxyHeaders=['X-Forwarded-For'])
    client = TestClient(app, raise_server_exceptions=False)

    firstResponse = client.post('/limited', json={'value': 'first'}, headers={'X-Forwarded-For': '9.9.9.9'})
    secondResponse = client.post('/limited', json={'value': 'second'}, headers={'X-Forwarded-For': '9.9.9.9'})
    otherIpResponse = client.post('/limited', json={'value': 'other'}, headers={'X-Forwarded-For': '8.8.8.8'})

    assert firstResponse.status_code == 200
    assert secondResponse.status_code == 429
    assert int(secondResponse.headers['retry-after']) >= 1
    assert otherIpResponse.status_code == 200


def test_rate_limit_ip_key_without_middleware_returns_500() -> None:
    @json_route(requestType=ExampleRequest, responseType=ExampleResponse)
    @rate_limit({'perMinute': 1, 'keyBy': 'ip'})
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    app = Starlette(routes=[Route('/limited', endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post('/limited', json={'value': 'first'})
    assert response.status_code == 500
