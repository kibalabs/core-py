from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from core.api.middleware.public_cors_middleware import PublicCorsMiddleware

ALLOWED_ORIGIN = 'https://app.example'
OTHER_ORIGIN = 'https://other.example'


def _build_client() -> TestClient:
    async def ok(request):
        return PlainTextResponse('ok')

    app = Starlette(routes=[Route('/public', ok), Route('/private', ok)])
    app.add_middleware(CORSMiddleware, allow_credentials=True, allow_methods=['*'], allow_headers=['*'], allow_origins=[ALLOWED_ORIGIN])
    app.add_middleware(PublicCorsMiddleware, paths={'/public'})
    return TestClient(app)


def test_public_path_answers_preflight_from_any_origin() -> None:
    client = _build_client()
    response = client.options('/public', headers={'Origin': OTHER_ORIGIN, 'Access-Control-Request-Method': 'GET'})
    assert response.status_code == 204
    assert response.headers['access-control-allow-origin'] == '*'
    assert response.headers['access-control-allow-methods'] == 'GET, OPTIONS'


def test_public_path_allows_any_origin() -> None:
    client = _build_client()
    response = client.get('/public', headers={'Origin': OTHER_ORIGIN})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == '*'


def test_public_path_keeps_the_cors_answer_for_an_allowed_origin() -> None:
    client = _build_client()
    response = client.get('/public', headers={'Origin': ALLOWED_ORIGIN})
    assert response.headers['access-control-allow-origin'] == ALLOWED_ORIGIN
    assert response.headers['access-control-allow-credentials'] == 'true'


def test_other_paths_keep_the_cors_policy() -> None:
    client = _build_client()
    preflightResponse = client.options('/private', headers={'Origin': OTHER_ORIGIN, 'Access-Control-Request-Method': 'GET'})
    assert preflightResponse.status_code == 400
    response = client.get('/private', headers={'Origin': OTHER_ORIGIN})
    assert 'access-control-allow-origin' not in response.headers
