import json
import pytest
from collections.abc import AsyncIterator
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from core.api.api_request import KibaApiRequest
from core.api.authorizer import Authorizer, SignatureAuthorizer, StaticTokenAuthorizer, authorize_bearer_jwt, authorize_signature, authorize_token
from core.api.json_route import json_route
from core.api.middleware.exception_handling_middleware import ExceptionHandlingMiddleware
from core.api.streaming_json_route import streaming_json_route
from core.exceptions import ForbiddenException
from core.http.jwt import Jwt


VALID_JWT_TOKEN = 'valid-token'
VALID_SIGNATURE = 'valid-sig'
VALID_STATIC_TOKEN = 'secret-token'
VALID_USER_ID = 'user-123'


class MockJwtAuthorizer(Authorizer):
    async def validate_jwt(self, jwtString: str) -> Jwt:
        if jwtString != VALID_JWT_TOKEN:
            raise ForbiddenException('Invalid token')
        jwt = Jwt(payloadDict={'sub': VALID_USER_ID})
        jwt.userId = VALID_USER_ID  # type: ignore[attr-defined]
        return jwt


class MockSignatureAuthorizer(SignatureAuthorizer):
    async def retrieve_signature_signer(self, signatureString: str) -> str:
        if signatureString != VALID_SIGNATURE:
            raise ForbiddenException('Invalid signature')
        return VALID_USER_ID


class SimpleRequest(BaseModel):
    value: str


class SimpleResponse(BaseModel):
    result: str
    user_id: str | None = None


jwt_authorizer = MockJwtAuthorizer()
sig_authorizer = MockSignatureAuthorizer()


# --- authorize_bearer_jwt fixtures ---

@pytest.fixture
def jwt_json_client():
    @json_route(requestType=SimpleRequest, responseType=SimpleResponse)
    @authorize_bearer_jwt(authorizer=jwt_authorizer)
    async def protected_endpoint(request: KibaApiRequest[SimpleRequest]) -> SimpleResponse:
        jwt = request.authJwt
        return SimpleResponse(result=request.data.value, user_id=getattr(jwt, 'userId', None))

    app = Starlette(routes=[Route('/protected', protected_endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def jwt_streaming_client():
    @streaming_json_route(requestType=SimpleRequest, responseType=SimpleResponse)
    @authorize_bearer_jwt(authorizer=jwt_authorizer)
    async def protected_streaming_endpoint(request: KibaApiRequest[SimpleRequest]) -> AsyncIterator[SimpleResponse]:
        jwt = request.authJwt
        yield SimpleResponse(result=request.data.value, user_id=getattr(jwt, 'userId', None))

    app = Starlette(routes=[Route('/protected-stream', protected_streaming_endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    return TestClient(app, raise_server_exceptions=False)


# --- authorize_signature fixtures ---

@pytest.fixture
def sig_json_client():
    @json_route(requestType=SimpleRequest, responseType=SimpleResponse)
    @authorize_signature(authorizer=sig_authorizer)
    async def protected_endpoint(request: KibaApiRequest[SimpleRequest]) -> SimpleResponse:
        return SimpleResponse(result=request.data.value, user_id=request.authBasic.username if request.authBasic else None)

    app = Starlette(routes=[Route('/protected', protected_endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def sig_streaming_client():
    @streaming_json_route(requestType=SimpleRequest, responseType=SimpleResponse)
    @authorize_signature(authorizer=sig_authorizer)
    async def protected_streaming_endpoint(request: KibaApiRequest[SimpleRequest]) -> AsyncIterator[SimpleResponse]:
        yield SimpleResponse(result=request.data.value, user_id=request.authBasic.username if request.authBasic else None)

    app = Starlette(routes=[Route('/protected-stream', protected_streaming_endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    return TestClient(app, raise_server_exceptions=False)


# --- authorize_token fixtures ---

token_authorizer = StaticTokenAuthorizer(token=VALID_STATIC_TOKEN)


@pytest.fixture
def token_json_client():
    @json_route(requestType=SimpleRequest, responseType=SimpleResponse)
    @authorize_token(authorizer=token_authorizer)
    async def protected_endpoint(request: KibaApiRequest[SimpleRequest]) -> SimpleResponse:
        return SimpleResponse(result=request.data.value)

    app = Starlette(routes=[Route('/protected', protected_endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def token_streaming_client():
    @streaming_json_route(requestType=SimpleRequest, responseType=SimpleResponse)
    @authorize_token(authorizer=token_authorizer)
    async def protected_streaming_endpoint(request: KibaApiRequest[SimpleRequest]) -> AsyncIterator[SimpleResponse]:
        yield SimpleResponse(result=request.data.value)

    app = Starlette(routes=[Route('/protected-stream', protected_streaming_endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    return TestClient(app, raise_server_exceptions=False)


# --- authorize_bearer_jwt + json_route ---

def test_jwt_json_no_auth_header_returns_403(jwt_json_client):
    response = jwt_json_client.post('/protected', json={'value': 'hello'})
    assert response.status_code == 403

def test_jwt_json_wrong_scheme_returns_403(jwt_json_client):
    response = jwt_json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': 'Basic creds'})
    assert response.status_code == 403

def test_jwt_json_invalid_token_returns_403(jwt_json_client):
    response = jwt_json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': 'Bearer bad-token'})
    assert response.status_code == 403

def test_jwt_json_valid_token_returns_200(jwt_json_client):
    response = jwt_json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': f'Bearer {VALID_JWT_TOKEN}'})
    assert response.status_code == 200
    assert response.json()['result'] == 'hello'

def test_jwt_json_sets_auth_jwt_on_request(jwt_json_client):
    response = jwt_json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': f'Bearer {VALID_JWT_TOKEN}'})
    assert response.status_code == 200
    assert response.json()['user_id'] == VALID_USER_ID


# --- authorize_bearer_jwt + streaming_json_route ---

def test_jwt_streaming_no_auth_header_returns_403(jwt_streaming_client):
    response = jwt_streaming_client.post('/protected-stream', json={'value': 'hello'})
    assert response.status_code == 403

def test_jwt_streaming_invalid_token_returns_403(jwt_streaming_client):
    response = jwt_streaming_client.post('/protected-stream', json={'value': 'hello'}, headers={'Authorization': 'Bearer bad-token'})
    assert response.status_code == 403

def test_jwt_streaming_valid_token_returns_200(jwt_streaming_client):
    response = jwt_streaming_client.post('/protected-stream', json={'value': 'hello'}, headers={'Authorization': f'Bearer {VALID_JWT_TOKEN}'})
    assert response.status_code == 200

def test_jwt_streaming_valid_token_streams_data(jwt_streaming_client):
    response = jwt_streaming_client.post('/protected-stream', json={'value': 'hello'}, headers={'Authorization': f'Bearer {VALID_JWT_TOKEN}'})
    data = json.loads(response.content.decode().strip())
    assert data['result'] == 'hello'
    assert data['user_id'] == VALID_USER_ID


# --- authorize_signature + json_route ---

def test_sig_json_no_auth_header_returns_403(sig_json_client):
    response = sig_json_client.post('/protected', json={'value': 'hello'})
    assert response.status_code == 403

def test_sig_json_wrong_scheme_returns_403(sig_json_client):
    response = sig_json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': 'Bearer something'})
    assert response.status_code == 403

def test_sig_json_invalid_signature_returns_403(sig_json_client):
    response = sig_json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': 'Signature bad-sig'})
    assert response.status_code == 403

def test_sig_json_valid_signature_returns_200(sig_json_client):
    response = sig_json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': f'Signature {VALID_SIGNATURE}'})
    assert response.status_code == 200
    assert response.json()['result'] == 'hello'

def test_sig_json_sets_auth_basic_on_request(sig_json_client):
    response = sig_json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': f'Signature {VALID_SIGNATURE}'})
    assert response.status_code == 200
    assert response.json()['user_id'] == VALID_USER_ID


# --- authorize_signature + streaming_json_route ---

def test_sig_streaming_no_auth_header_returns_403(sig_streaming_client):
    response = sig_streaming_client.post('/protected-stream', json={'value': 'hello'})
    assert response.status_code == 403

def test_sig_streaming_invalid_signature_returns_403(sig_streaming_client):
    response = sig_streaming_client.post('/protected-stream', json={'value': 'hello'}, headers={'Authorization': 'Signature bad-sig'})
    assert response.status_code == 403

def test_sig_streaming_valid_signature_returns_200(sig_streaming_client):
    response = sig_streaming_client.post('/protected-stream', json={'value': 'hello'}, headers={'Authorization': f'Signature {VALID_SIGNATURE}'})
    assert response.status_code == 200

def test_sig_streaming_valid_signature_streams_data(sig_streaming_client):
    response = sig_streaming_client.post('/protected-stream', json={'value': 'hello'}, headers={'Authorization': f'Signature {VALID_SIGNATURE}'})
    data = json.loads(response.content.decode().strip())
    assert data['result'] == 'hello'
    assert data['user_id'] == VALID_USER_ID


# --- authorize_token + json_route ---

def test_token_json_no_auth_header_returns_403(token_json_client):
    response = token_json_client.post('/protected', json={'value': 'hello'})
    assert response.status_code == 403

def test_token_json_wrong_scheme_returns_403(token_json_client):
    response = token_json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': 'Bearer something'})
    assert response.status_code == 403

def test_token_json_invalid_token_returns_403(token_json_client):
    response = token_json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': 'Token wrong-token'})
    assert response.status_code == 403

def test_token_json_valid_token_returns_200(token_json_client):
    response = token_json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': f'Token {VALID_STATIC_TOKEN}'})
    assert response.status_code == 200
    assert response.json()['result'] == 'hello'


# --- authorize_token + streaming_json_route ---

def test_token_streaming_no_auth_header_returns_403(token_streaming_client):
    response = token_streaming_client.post('/protected-stream', json={'value': 'hello'})
    assert response.status_code == 403

def test_token_streaming_invalid_token_returns_403(token_streaming_client):
    response = token_streaming_client.post('/protected-stream', json={'value': 'hello'}, headers={'Authorization': 'Token wrong-token'})
    assert response.status_code == 403

def test_token_streaming_valid_token_returns_200(token_streaming_client):
    response = token_streaming_client.post('/protected-stream', json={'value': 'hello'}, headers={'Authorization': f'Token {VALID_STATIC_TOKEN}'})
    assert response.status_code == 200

def test_token_streaming_valid_token_streams_data(token_streaming_client):
    response = token_streaming_client.post('/protected-stream', json={'value': 'hello'}, headers={'Authorization': f'Token {VALID_STATIC_TOKEN}'})
    data = json.loads(response.content.decode().strip())
    assert data['result'] == 'hello'
