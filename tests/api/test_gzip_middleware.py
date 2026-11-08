from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from core.api.middleware.gzip_middleware import GZipMiddleware


def _build_client() -> TestClient:
    async def large(request):
        return PlainTextResponse('x' * 2000)

    app = Starlette(routes=[Route('/login', large), Route('/files/create-upload', large), Route('/items', large)])
    app.add_middleware(GZipMiddleware, minimum_size=1000, excludedPaths={'/login'}, excludedPathSuffixes=('/create-upload',))
    return TestClient(app)


def test_compresses_paths_that_are_not_excluded() -> None:
    response = _build_client().get('/items', headers={'Accept-Encoding': 'gzip'})
    assert response.headers.get('content-encoding') == 'gzip'


def test_does_not_compress_excluded_paths() -> None:
    client = _build_client()
    for path in ('/login', '/files/create-upload'):
        response = client.get(path, headers={'Accept-Encoding': 'gzip'})
        assert 'content-encoding' not in response.headers
        assert response.text == 'x' * 2000
