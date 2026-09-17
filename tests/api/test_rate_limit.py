from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from core.api.api_request import KibaApiRequest
from core.api.json_route import json_route
from core.api.rate_limit import rate_limit
from core.api.route_metadata import get_route_metadata
from core.api.middleware.exception_handling_middleware import ExceptionHandlingMiddleware


class ExampleRequest(BaseModel):
    value: str


class ExampleResponse(BaseModel):
    result: str


def test_rate_limit_uses_injected_key_and_publishes_metadata() -> None:
    @json_route(requestType=ExampleRequest, responseType=ExampleResponse)
    @rate_limit(perMinute=1, keyFunction=lambda request: request.headers.get('x-caller', 'missing'))
    async def limited_endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    app = Starlette(routes=[Route('/limited', limited_endpoint, methods=['POST'])])
    app.add_middleware(ExceptionHandlingMiddleware)
    client = TestClient(app, raise_server_exceptions=False)

    firstResponse = client.post('/limited', json={'value': 'first'}, headers={'X-Caller': 'caller-1'})
    secondResponse = client.post('/limited', json={'value': 'second'}, headers={'X-Caller': 'caller-1'})
    otherCallerResponse = client.post('/limited', json={'value': 'other'}, headers={'X-Caller': 'caller-2'})

    assert firstResponse.status_code == 200
    assert secondResponse.status_code == 429
    assert int(secondResponse.headers['retry-after']) >= 1
    assert otherCallerResponse.status_code == 200
    assert get_route_metadata(limited_endpoint)['rateLimit'] == {'perMinute': 1}
