import functools
import typing
from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable

from pydantic import BaseModel

from core.api.api_request import KibaApiRequest
from core.util.value_holder import ContextSettableValueHolder

_AnyReturn = typing.Awaitable[typing.Any] | AsyncIterator[typing.Any]  # type: ignore[explicit-any]


@typing.overload
def with_request_context[RequestModel: BaseModel, ContextType, ResponseType](
    contextHolder: ContextSettableValueHolder[ContextType],
    contextFactory: Callable[[KibaApiRequest[RequestModel]], Awaitable[ContextType]],
) -> Callable[
    [Callable[[KibaApiRequest[RequestModel]], Awaitable[ResponseType]]],
    Callable[[KibaApiRequest[RequestModel]], Awaitable[ResponseType]],
]: ...


@typing.overload
def with_request_context[RequestModel: BaseModel, ContextType, ResponseType](
    contextHolder: ContextSettableValueHolder[ContextType],
    contextFactory: Callable[[KibaApiRequest[RequestModel]], Awaitable[ContextType]],
) -> Callable[
    [Callable[[KibaApiRequest[RequestModel]], AsyncIterator[ResponseType]]],
    Callable[[KibaApiRequest[RequestModel]], Awaitable[AsyncIterator[ResponseType]]],
]: ...


def with_request_context[RequestModel: BaseModel, ContextType](  # type: ignore[explicit-any]
    contextHolder: ContextSettableValueHolder[ContextType],
    contextFactory: Callable[[KibaApiRequest[RequestModel]], Awaitable[ContextType]],
) -> Callable[
    [Callable[[KibaApiRequest[RequestModel]], _AnyReturn]],
    Callable[[KibaApiRequest[RequestModel]], typing.Any],
]:
    def decorator(func: Callable[[KibaApiRequest[RequestModel]], _AnyReturn]) -> Callable[[KibaApiRequest[RequestModel]], typing.Any]:  # type: ignore[explicit-any]
        @functools.wraps(func)
        async def wrapped(request: KibaApiRequest[RequestModel]) -> typing.Any:  # type: ignore[explicit-any, misc]
            context = await contextFactory(request)
            previousContext = contextHolder.get_value()
            contextHolder.set_value(context)
            result = func(request)
            if hasattr(result, '__aiter__'):

                async def stream() -> typing.AsyncIterator[typing.Any]:  # type: ignore[explicit-any]
                    try:
                        async for item in typing.cast(AsyncIterator[typing.Any], result):
                            yield item
                    finally:
                        contextHolder.set_value(previousContext)

                return stream()
            try:
                return await result
            finally:
                contextHolder.set_value(previousContext)

        return wrapped

    return decorator
