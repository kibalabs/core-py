import pytest
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from core.api.api_request import KibaApiRequest
from core.api.json_route import json_route
from core.api.middleware.exception_handling_middleware import ExceptionHandlingMiddleware
from core.api.request_context import RequestContext
from core.api.request_context import RequestContextHolder
from core.api.request_context import RequestContextMiddleware
from core.api.request_context import create_request_context
from core.exceptions import BadRequestException
from core.exceptions import FoundRedirectException
from core.exceptions import MovedPermanentlyRedirectException
from core.exceptions import TooManyRequestsException


requestContextHolder = RequestContextHolder[RequestContext]()


class SimpleRequest(BaseModel):
    value: str


class SimpleResponse(BaseModel):
    result: str


@pytest.fixture
def rate_limited_client():
    @json_route(requestType=SimpleRequest, responseType=SimpleResponse)
    async def limited_endpoint(request: KibaApiRequest[SimpleRequest]) -> SimpleResponse:
        raise TooManyRequestsException(message='slow down', retryAfterSeconds=30)

    app = Starlette(routes=[Route('/limited', limited_endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    app.add_middleware(RequestContextMiddleware, requestContextHolder=requestContextHolder, requestContextFactory=create_request_context)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def rate_limited_no_retry_client():
    @json_route(requestType=SimpleRequest, responseType=SimpleResponse)
    async def limited_endpoint(request: KibaApiRequest[SimpleRequest]) -> SimpleResponse:
        raise TooManyRequestsException(message='slow down')

    app = Starlette(routes=[Route('/limited', limited_endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    app.add_middleware(RequestContextMiddleware, requestContextHolder=requestContextHolder, requestContextFactory=create_request_context)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def found_redirect_client():
    @json_route(requestType=SimpleRequest, responseType=SimpleResponse)
    async def redirect_endpoint(request: KibaApiRequest[SimpleRequest]) -> SimpleResponse:
        raise FoundRedirectException(location='https://example.com/elsewhere')

    app = Starlette(routes=[Route('/redirect', redirect_endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    app.add_middleware(RequestContextMiddleware, requestContextHolder=requestContextHolder, requestContextFactory=create_request_context)
    return TestClient(app, raise_server_exceptions=False, follow_redirects=False)


@pytest.fixture
def permanent_redirect_client():
    @json_route(requestType=SimpleRequest, responseType=SimpleResponse)
    async def redirect_endpoint(request: KibaApiRequest[SimpleRequest]) -> SimpleResponse:
        raise MovedPermanentlyRedirectException(location='https://example.com/moved')

    app = Starlette(routes=[Route('/redirect', redirect_endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    app.add_middleware(RequestContextMiddleware, requestContextHolder=requestContextHolder, requestContextFactory=create_request_context)
    return TestClient(app, raise_server_exceptions=False, follow_redirects=False)


@pytest.fixture
def plain_error_client():
    @json_route(requestType=SimpleRequest, responseType=SimpleResponse)
    async def failing_endpoint(request: KibaApiRequest[SimpleRequest]) -> SimpleResponse:
        raise BadRequestException(message='bad input')

    app = Starlette(routes=[Route('/fail', failing_endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    app.add_middleware(RequestContextMiddleware, requestContextHolder=requestContextHolder, requestContextFactory=create_request_context)
    return TestClient(app, raise_server_exceptions=False)


def test_too_many_requests_returns_429_with_retry_after_header(rate_limited_client):
    response = rate_limited_client.post('/limited', json={'value': 'hello'})
    assert response.status_code == 429
    assert response.headers['retry-after'] == '30'


def test_too_many_requests_without_retry_after_omits_header(rate_limited_no_retry_client):
    response = rate_limited_no_retry_client.post('/limited', json={'value': 'hello'})
    assert response.status_code == 429
    assert 'retry-after' not in response.headers


def test_found_redirect_sets_location_without_cache_header(found_redirect_client):
    response = found_redirect_client.post('/redirect', json={'value': 'hello'})
    assert response.status_code == 302
    assert response.headers['location'] == 'https://example.com/elsewhere'
    assert 'cache-control' not in response.headers


def test_permanent_redirect_sets_location_and_cache_header(permanent_redirect_client):
    response = permanent_redirect_client.post('/redirect', json={'value': 'hello'})
    assert response.status_code == 301
    assert response.headers['location'] == 'https://example.com/moved'
    assert response.headers['cache-control'] == f'max-age={60 * 60 * 24 * 365}'


def test_plain_exception_has_no_extra_headers(plain_error_client):
    response = plain_error_client.post('/fail', json={'value': 'hello'})
    assert response.status_code == 400
    assert 'retry-after' not in response.headers
    assert 'location' not in response.headers
