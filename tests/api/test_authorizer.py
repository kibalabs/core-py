import pytest
from collections.abc import AsyncIterator
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from core.api.api_request import KibaApiRequest
from core.api.authorizer import Authorizer, authorize_bearer_jwt
from core.api.json_route import json_route
from core.api.middleware.exception_handling_middleware import ExceptionHandlingMiddleware
from core.api.streaming_json_route import streaming_json_route
from core.exceptions import ForbiddenException
from core.http.jwt import Jwt


VALID_TOKEN = 'valid-token'
VALID_USER_ID = 'user-123'


class MockAuthorizer(Authorizer):
    async def validate_jwt(self, jwtString: str) -> Jwt:
        if jwtString != VALID_TOKEN:
            raise ForbiddenException('Invalid token')
        jwt = Jwt(payloadDict={'sub': VALID_USER_ID})
        jwt.userId = VALID_USER_ID  # type: ignore[attr-defined]
        return jwt


class SimpleRequest(BaseModel):
    value: str


class SimpleResponse(BaseModel):
    result: str
    user_id: str | None = None


authorizer = MockAuthorizer()


@pytest.fixture
def json_client():
    @json_route(requestType=SimpleRequest, responseType=SimpleResponse)
    @authorize_bearer_jwt(authorizer=authorizer)
    async def protected_endpoint(request: KibaApiRequest[SimpleRequest]) -> SimpleResponse:
        jwt = request.authJwt
        return SimpleResponse(result=request.data.value, user_id=getattr(jwt, 'userId', None))

    app = Starlette(routes=[Route('/protected', protected_endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def streaming_client():
    @streaming_json_route(requestType=SimpleRequest, responseType=SimpleResponse)
    @authorize_bearer_jwt(authorizer=authorizer)
    async def protected_streaming_endpoint(request: KibaApiRequest[SimpleRequest]) -> AsyncIterator[SimpleResponse]:
        jwt = request.authJwt
        yield SimpleResponse(result=request.data.value, user_id=getattr(jwt, 'userId', None))

    app = Starlette(routes=[Route('/protected-stream', protected_streaming_endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    return TestClient(app, raise_server_exceptions=False)


# --- json_route + authorize_bearer_jwt ---

def test_json_no_auth_header_returns_403(json_client):
    response = json_client.post('/protected', json={'value': 'hello'})
    assert response.status_code == 403


def test_json_malformed_auth_header_not_bearer_returns_403(json_client):
    response = json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': 'Basic some-creds'})
    assert response.status_code == 403


def test_json_bearer_with_no_token_returns_403(json_client):
    response = json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': 'Bearer '})
    assert response.status_code == 403


def test_json_invalid_token_returns_403(json_client):
    response = json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': 'Bearer bad-token'})
    assert response.status_code == 403


def test_json_valid_token_returns_200(json_client):
    response = json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': f'Bearer {VALID_TOKEN}'})
    assert response.status_code == 200
    assert response.json()['result'] == 'hello'


def test_json_valid_token_sets_auth_jwt_on_request(json_client):
    response = json_client.post('/protected', json={'value': 'hello'}, headers={'Authorization': f'Bearer {VALID_TOKEN}'})
    assert response.status_code == 200
    assert response.json()['user_id'] == VALID_USER_ID


def test_json_missing_request_body_field_returns_400(json_client):
    response = json_client.post('/protected', json={}, headers={'Authorization': f'Bearer {VALID_TOKEN}'})
    assert response.status_code == 400


# --- streaming_json_route + authorize_bearer_jwt ---

def test_streaming_no_auth_header_returns_403(streaming_client):
    response = streaming_client.post('/protected-stream', json={'value': 'hello'})
    assert response.status_code == 403


def test_streaming_malformed_auth_header_not_bearer_returns_403(streaming_client):
    response = streaming_client.post('/protected-stream', json={'value': 'hello'}, headers={'Authorization': 'Basic some-creds'})
    assert response.status_code == 403


def test_streaming_bearer_with_no_token_returns_403(streaming_client):
    response = streaming_client.post('/protected-stream', json={'value': 'hello'}, headers={'Authorization': 'Bearer '})
    assert response.status_code == 403


def test_streaming_invalid_token_returns_403(streaming_client):
    response = streaming_client.post('/protected-stream', json={'value': 'hello'}, headers={'Authorization': 'Bearer bad-token'})
    assert response.status_code == 403


def test_streaming_valid_token_returns_200(streaming_client):
    response = streaming_client.post('/protected-stream', json={'value': 'hello'}, headers={'Authorization': f'Bearer {VALID_TOKEN}'})
    assert response.status_code == 200


def test_streaming_valid_token_streams_correct_data(streaming_client):
    response = streaming_client.post('/protected-stream', json={'value': 'hello'}, headers={'Authorization': f'Bearer {VALID_TOKEN}'})
    assert response.status_code == 200
    import json
    lines = [l for l in response.content.decode().strip().split('\n') if l]
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data['result'] == 'hello'


def test_streaming_valid_token_sets_auth_jwt_on_request(streaming_client):
    response = streaming_client.post('/protected-stream', json={'value': 'hello'}, headers={'Authorization': f'Bearer {VALID_TOKEN}'})
    assert response.status_code == 200
    import json
    data = json.loads(response.content.decode().strip())
    assert data['user_id'] == VALID_USER_ID


def test_streaming_missing_request_body_field_returns_400(streaming_client):
    response = streaming_client.post('/protected-stream', json={}, headers={'Authorization': f'Bearer {VALID_TOKEN}'})
    assert response.status_code == 400
