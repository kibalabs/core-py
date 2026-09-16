import datetime

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route
from starlette.testclient import TestClient

from core.api.api_response import KibaJSONResponse
from core.api.default_routes import create_default_routes
from core.api.middleware.exception_handling_middleware import ExceptionHandlingMiddleware
from core.exceptions import BadRequestException


def test_kiba_json_response_uses_compact_utf8_serialization():
    response = KibaJSONResponse(content={'message': 'Hello 🌍', 'createdAt': datetime.datetime(2025, 1, 2, 3, 4, 5), 'values': [1, 2]})

    assert response.body == '{"message":"Hello 🌍","createdAt":"2025-01-02T03:04:05","values":[1,2]}'.encode()


def test_default_route_uses_kiba_json_response():
    app = Starlette(routes=create_default_routes(name='core', version='1.0', environment='test'))
    client = TestClient(app)

    response = client.get('/')

    assert response.content == b'{"server":"core","version":"1.0","environment":"test"}'


def test_exception_handling_middleware_uses_kiba_json_response():
    async def failing_endpoint(_request: Request) -> KibaJSONResponse:
        raise BadRequestException(message='bad input')

    app = Starlette(routes=[Route('/fail', failing_endpoint)])
    app.add_middleware(ExceptionHandlingMiddleware)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get('/fail')

    assert response.content == b'{"exceptionType":"BadRequestException","message":"bad input","fields":{},"statusCode":400}'
