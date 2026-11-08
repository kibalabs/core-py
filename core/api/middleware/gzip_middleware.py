from collections.abc import Collection

from starlette.middleware import gzip
from starlette.types import ASGIApp
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send


class GZipMiddleware(gzip.GZipMiddleware):
    # NOTE(krishan711): exclude responses that carry secrets (tokens, signed urls): compressing them enables BREACH
    def __init__(self, app: ASGIApp, minimum_size: int = 500, compresslevel: int = 9, excludedPaths: Collection[str] = (), excludedPathSuffixes: Collection[str] = ()) -> None:
        super().__init__(app=app, minimum_size=minimum_size, compresslevel=compresslevel)
        self.excludedPaths = frozenset(excludedPaths)
        self.excludedPathSuffixes = tuple(excludedPathSuffixes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] == 'http' and (scope['path'] in self.excludedPaths or scope['path'].endswith(self.excludedPathSuffixes)):
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)
