import contextvars
import typing
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass

from starlette.types import ASGIApp
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send


@dataclass
class RequestContext:
    originIp: str | None


def create_request_context(scope: Scope) -> RequestContext:
    return RequestContext(originIp=typing.cast('str | None', scope.get('originIp')))


class RequestContextHolder[RequestContextType: RequestContext]:
    def __init__(self) -> None:
        self._valueContext = contextvars.ContextVar[RequestContextType | None]('_valueContext', default=None)

    def get_value(self) -> RequestContextType:
        value = self._valueContext.get()
        if value is None:
            raise RuntimeError('No request context is active')
        return value

    @contextmanager
    def use_value(self, value: RequestContextType) -> typing.Iterator[RequestContextType]:
        token = self._valueContext.set(value)
        try:
            yield value
        finally:
            self._valueContext.reset(token)


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp, requestContextHolder: RequestContextHolder[typing.Any], requestContextFactory: Callable[[Scope], RequestContext]) -> None:  # type: ignore[explicit-any]
        self.app = app
        self.requestContextHolder = requestContextHolder
        self.requestContextFactory = requestContextFactory
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        with self.requestContextHolder.use_value(self.requestContextFactory(scope)):
            await self.app(scope, receive, send)
