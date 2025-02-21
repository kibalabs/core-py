from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.responses import Response
from starlette.routing import BaseRoute
from starlette.routing import Route


def create_default_routes(name: str, version: str, environment: str) -> list[BaseRoute]:
    async def root(request: Request) -> Response:  # noqa: ARG001
        return JSONResponse(content={'server': name, 'version': version, 'environment': environment})

    return [
        Route('/', methods=['GET'], endpoint=root),
    ]
