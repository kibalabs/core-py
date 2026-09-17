import functools

import json

from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from core.api.api_request import KibaApiRequest
from core.api.authorizer import SignatureAuthorizer
from core.api.authorizer import authorize_signature
from core.api.middleware.exception_handling_middleware import ExceptionHandlingMiddleware
from core.api.middleware.origin_ip_middleware import OriginIpMiddleware
from core.api.route import route
from core.api.route_metadata import RateLimitConfig
from core.api.route_metadata import SecurityScheme
from core.api.route_metadata import get_route_metadata


class ExampleRequest(BaseModel):
    value: str


class ExampleResponse(BaseModel):
    result: str


VALID_SIGNATURE = 'valid-sig'
VALID_SIGNER_ID = 'signer-123'
EXAMPLE_SECURITY_SCHEME = SecurityScheme(name='ExampleApiKey', definition={'type': 'apiKey', 'in': 'header', 'name': 'Authorization'})


class MockSignatureAuthorizer(SignatureAuthorizer):
    async def retrieve_signature_signer(self, signatureString: str) -> str:
        if signatureString != VALID_SIGNATURE:
            raise ValueError('invalid signature')
        return VALID_SIGNER_ID


sig_authorizer = MockSignatureAuthorizer()


def _build_client(*, isStreaming: bool, rateLimit: RateLimitConfig | None = None, auth: tuple = ()) -> TestClient:
    if isStreaming:

        @route(requestType=ExampleRequest, responseType=ExampleResponse, isStreaming=True, operationId='streamExample', tags=['Examples'], auth=auth, rateLimit=rateLimit)
        async def endpoint(request: KibaApiRequest[ExampleRequest]):
            yield ExampleResponse(result=request.data.value)
    else:

        @route(requestType=ExampleRequest, responseType=ExampleResponse, operationId='getExample', tags=['Examples'], auth=auth, rateLimit=rateLimit)
        async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
            return ExampleResponse(result=request.data.value)

    app = Starlette(routes=[Route('/example', endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    app.add_middleware(OriginIpMiddleware)
    return TestClient(app, raise_server_exceptions=False)

def _record_auth(events: list[str], name: str):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(request):
            events.append(name)
            return await func(request)

        return wrapper

    return decorator



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


def test_route_publishes_openapi_metadata() -> None:
    @route(
        requestType=ExampleRequest,
        responseType=ExampleResponse,
        operationId='getExample',
        summary='Get an example',
        description='An example endpoint.',
        tags=['Examples'],
        auth=(authorize_signature(authorizer=sig_authorizer, securityScheme=EXAMPLE_SECURITY_SCHEME),),
        rateLimit={'perMinute': 3, 'perHour': 30},
    )
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    metadata = get_route_metadata(endpoint)
    assert metadata['operationId'] == 'getExample'
    assert metadata['summary'] == 'Get an example'
    assert metadata['description'] == 'An example endpoint.'
    assert metadata['tags'] == ['Examples']
    assert metadata['security'] == [{'ExampleApiKey': []}]
    assert metadata['rateLimit'] == {'perMinute': 3, 'perHour': 30}
    assert metadata['streamed'] is False


def test_route_enforces_rate_limit_using_the_same_logic_as_rate_limit_decorator() -> None:
    client = _build_client(isStreaming=False, rateLimit={'perMinute': 1, 'keyBy': 'ip'})

    first = client.post('/example', json={'value': 'first'})
    second = client.post('/example', json={'value': 'second'})

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers['retry-after']) >= 1


def test_route_rate_limit_defaults_to_keying_by_user() -> None:
    client = _build_client(isStreaming=False, rateLimit={'perMinute': 1})

    response = client.post('/example', json={'value': 'x'})

    assert response.status_code == 500  # no auth decorator ran, so keyBy='user' has nothing to key on


def test_route_without_rate_limit_does_not_enforce_any_limit() -> None:
    client = _build_client(isStreaming=False)
    for _ in range(5):
        response = client.post('/example', json={'value': 'x'})
        assert response.status_code == 200


def test_route_composed_auth_runs_before_rate_limit() -> None:
    # keyBy='user' needs request.authBasic, which only an auth decorator sets - proves auth
    # decorators run before rate_limit, not after, when both are composed onto route().
    client = _build_client(isStreaming=False, auth=(authorize_signature(authorizer=sig_authorizer),), rateLimit={'perMinute': 1})

    first = client.post('/example', json={'value': 'first'}, headers={'Authorization': f'Signature {VALID_SIGNATURE}'})
    second = client.post('/example', json={'value': 'second'}, headers={'Authorization': f'Signature {VALID_SIGNATURE}'})

    assert first.status_code == 200
    assert second.status_code == 429


def test_route_composed_auth_rejects_unauthenticated_requests() -> None:
    client = _build_client(isStreaming=False, auth=(authorize_signature(authorizer=sig_authorizer),))

    response = client.post('/example', json={'value': 'x'})

    assert response.status_code == 403


def test_route_composed_auth_accepts_valid_signature() -> None:
    client = _build_client(isStreaming=False, auth=(authorize_signature(authorizer=sig_authorizer),))

    response = client.post('/example', json={'value': 'hello'}, headers={'Authorization': f'Signature {VALID_SIGNATURE}'})

    assert response.status_code == 200
    assert response.json() == {'result': 'hello'}

def test_route_composes_auth_in_declaration_order() -> None:
    events: list[str] = []
    client = _build_client(isStreaming=False, auth=(_record_auth(events, 'user'), _record_auth(events, 'integrator')))

    response = client.post('/example', json={'value': 'hello'})

    assert response.status_code == 200
    assert events == ['user', 'integrator']
