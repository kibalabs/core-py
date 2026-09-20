import functools
import json

import pytest
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from core.api.api_request import KibaApiRequest
from core.api.authorizer import SignatureAuthorizer
from core.api.authorizer import authorize_static_token_request
from core.api.authorizer import get_basic_authentication_from_authorization_signature
from core.api.middleware.exception_handling_middleware import ExceptionHandlingMiddleware
from core.api.middleware.origin_ip_middleware import OriginIpMiddleware
from core.api.route import route as api_route
from core.api.route_auth import RouteAuthResolver
from core.api.route_metadata import RateLimitConfig


class ExampleRequest(BaseModel):
    value: str


class ExampleResponse(BaseModel):
    result: str


VALID_SIGNATURE = 'valid-sig'
VALID_STATIC_TOKEN = 'static-token'
VALID_SIGNER_ID = 'signer-123'


class MockSignatureAuthorizer(SignatureAuthorizer):
    async def retrieve_signature_signer(self, signatureString: str) -> str:
        if signatureString != VALID_SIGNATURE:
            raise ValueError('invalid signature')
        return VALID_SIGNER_ID


sig_authorizer = MockSignatureAuthorizer()


class ExampleRouteAuthResolver(RouteAuthResolver):
    async def authorize_route(self, *, auth: str, request: KibaApiRequest[BaseModel]) -> None:
        if auth == 'signature':
            request.authBasic = await get_basic_authentication_from_authorization_signature(request=request, authorizer=sig_authorizer)
            return
        if auth == 'static_token':
            await authorize_static_token_request(request=request, token=VALID_STATIC_TOKEN)
            return
        raise ValueError(f'Unknown auth policy: {auth}')

    def get_route_security_schemes(self, *, auth: str) -> list[str]:
        if auth in {'signature', 'static_token'}:
            return []
        raise ValueError(f'Unknown auth policy: {auth}')


def _build_client(
    *,
    isStreaming: bool,
    rateLimit: RateLimitConfig | None = None,
    auth: str | None = None,
    endpointCalls: list[str] | None = None,
) -> TestClient:
    route = functools.partial(api_route, authResolver=ExampleRouteAuthResolver())
    if isStreaming:

        @route(requestType=ExampleRequest, responseType=ExampleResponse, isStreaming=True, operationId='streamExample', tags=['Examples'], auth=auth, rateLimit=rateLimit)
        async def endpoint(request: KibaApiRequest[ExampleRequest]):
            if endpointCalls is not None:
                endpointCalls.append(request.data.value)
            yield ExampleResponse(result=request.data.value)
    else:

        @route(requestType=ExampleRequest, responseType=ExampleResponse, operationId='getExample', tags=['Examples'], auth=auth, rateLimit=rateLimit)
        async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
            if endpointCalls is not None:
                endpointCalls.append(request.data.value)
            return ExampleResponse(result=request.data.value)

    app = Starlette(routes=[Route('/example', endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    app.add_middleware(OriginIpMiddleware)
    return TestClient(app, raise_server_exceptions=False)


def test_route_handles_json_requests() -> None:
    client = _build_client(isStreaming=False)
    response = client.post('/example', json={'value': 'hello'})
    assert response.status_code == 200
    assert response.json() == {'result': 'hello'}


def test_route_handles_streaming_requests() -> None:
    client = _build_client(isStreaming=True)
    response = client.post('/example', json={'value': 'hello'})
    assert response.status_code == 200
    assert json.loads(response.content.decode().strip()) == {'result': 'hello'}




def test_route_enforces_rate_limit_using_the_same_logic_as_rate_limit_decorator() -> None:
    client = _build_client(isStreaming=False, rateLimit={'perMinute': 1, 'keyBy': 'ip'})

    first = client.post('/example', json={'value': 'first'})
    second = client.post('/example', json={'value': 'second'})

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers['retry-after']) >= 1




def test_route_without_rate_limit_does_not_enforce_any_limit() -> None:
    client = _build_client(isStreaming=False)
    for _ in range(5):
        response = client.post('/example', json={'value': 'x'})
        assert response.status_code == 200


def test_route_authenticates_before_rate_limiting() -> None:
    client = _build_client(isStreaming=False, auth='signature', rateLimit={'perMinute': 1})

    first = client.post('/example', json={'value': 'first'}, headers={'Authorization': f'Signature {VALID_SIGNATURE}'})
    second = client.post('/example', json={'value': 'second'}, headers={'Authorization': f'Signature {VALID_SIGNATURE}'})

    assert first.status_code == 200
    assert second.status_code == 429


def test_route_rejects_unauthenticated_requests_before_calling_endpoint() -> None:
    endpointCalls: list[str] = []
    client = _build_client(isStreaming=False, auth='signature', endpointCalls=endpointCalls)

    response = client.post('/example', json={'value': 'x'})

    assert response.status_code == 403
    assert endpointCalls == []


def test_streaming_route_rejects_unauthenticated_requests_before_starting_stream() -> None:
    endpointCalls: list[str] = []
    client = _build_client(isStreaming=True, auth='signature', endpointCalls=endpointCalls)

    response = client.post('/example', json={'value': 'x'})

    assert response.status_code == 403
    assert endpointCalls == []


@pytest.mark.parametrize('authorization', [None, 'Bearer token', 'Token wrong-token'])
def test_route_static_token_policy_rejects_invalid_credentials_before_calling_endpoint(authorization: str | None) -> None:
    endpointCalls: list[str] = []
    client = _build_client(isStreaming=False, auth='static_token', endpointCalls=endpointCalls)
    headers = {} if authorization is None else {'Authorization': authorization}

    response = client.post('/example', json={'value': 'x'}, headers=headers)

    assert response.status_code == 403
    assert endpointCalls == []


def test_route_static_token_policy_accepts_valid_credentials() -> None:
    endpointCalls: list[str] = []
    client = _build_client(isStreaming=False, auth='static_token', endpointCalls=endpointCalls)

    response = client.post('/example', json={'value': 'hello'}, headers={'Authorization': f'Token {VALID_STATIC_TOKEN}'})

    assert response.status_code == 200
    assert response.json() == {'result': 'hello'}
    assert endpointCalls == ['hello']

def test_route_rejects_unknown_auth_policy_during_registration() -> None:
    with pytest.raises(ValueError, match='Unknown auth policy: unknown'):
        api_route(
            requestType=ExampleRequest,
            responseType=ExampleResponse,
            authResolver=ExampleRouteAuthResolver(),
            auth='unknown',
        )
