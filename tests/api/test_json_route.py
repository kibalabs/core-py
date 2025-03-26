import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from pydantic import BaseModel

from core.api.json_route import json_route
from core.api.api_request import KibaApiRequest
from core.api.middleware.exception_handling_middleware import ExceptionHandlingMiddleware


class ExampleRequest(BaseModel):
    name: str
    age: int
    tags: list[str] | None = None
    path_param: str | None = None


class ExampleResponse(BaseModel):
    message: str
    request_name: str
    request_age: int
    path_echo: str | None = None


@pytest.fixture
def client():
    @json_route(requestType=ExampleRequest, responseType=ExampleResponse)
    async def test_endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(
            message="Hello, world!",
            request_name=request.data.name,
            request_age=request.data.age,
            path_echo=request.data.path_param,
        )


    @json_route(requestType=ExampleRequest, responseType=ExampleResponse)
    async def test_path_endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(
            message="Path parameter received",
            request_name=request.data.name,
            request_age=request.data.age,
            path_echo=request.data.path_param,
        )


    app = Starlette(routes=[
        Route("/test", test_endpoint, methods=["POST"]),
        Route("/test/{path_param}", test_path_endpoint, methods=["POST"]),
    ])
    app.add_middleware(ExceptionHandlingMiddleware)
    return TestClient(app, raise_server_exceptions=False)


def test_json_route_with_valid_body(client):
    response = client.post(
        "/test",
        json={"name": "Test User", "age": 30, "tags": ["tag1", "tag2"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Hello, world!"
    assert data["request_name"] == "Test User"
    assert data["request_age"] == 30


def test_json_route_with_path_params(client):
    response = client.post(
        "/test/param-value",
        json={"name": "Test User", "age": 30}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["path_echo"] == "param-value"
    assert data["request_name"] == "Test User"


def test_json_route_with_query_params(client):
    response = client.post(
        "/test?name=QueryUser&age=25",
        json={}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["request_name"] == "QueryUser"
    assert data["request_age"] == 25


def test_json_route_with_invalid_json(client):
    response = client.post(
        "/test",
        content="invalid json",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert "Invalid JSON body" in response.json().get("message", "")


def test_json_route_with_validation_error_missing_field(client):
    response = client.post(
        "/test",
        json={"name": "Test User"}
    )
    assert response.status_code == 400
    assert "Invalid request" in response.json().get("message", "")


def test_json_route_combining_params(client):
    response = client.post(
        "/test/path-value?age=40",
        json={"name": "Combined User"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["path_echo"] == "path-value"
    assert data["request_name"] == "Combined User"
    assert data["request_age"] == 40


def test_json_route_empty_body(client):
    response = client.post(
        "/test?name=EmptyBody&age=50",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["request_name"] == "EmptyBody"
    assert data["request_age"] == 50
