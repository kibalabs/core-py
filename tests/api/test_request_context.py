from collections.abc import AsyncIterator

import pytest
from pydantic import BaseModel

from core.api.api_request import KibaApiRequest
from core.api.request_context import with_request_context
from core.util.value_holder import ContextSettableValueHolder


class ExampleRequest(BaseModel):
    value: str


async def _receive() -> dict[str, object]:
    return {'type': 'http.request'}


async def _send(message: dict[str, object]) -> None:
    del message


def _request() -> KibaApiRequest[ExampleRequest]:
    request = KibaApiRequest(scope={'type': 'http', 'headers': []}, receive=_receive, send=_send)
    request.data = ExampleRequest(value='value')
    return request


@pytest.mark.asyncio
async def test_with_request_context_restores_context_after_async_handler() -> None:
    holder = ContextSettableValueHolder[str | None](defaultValue=None)

    async def context_factory(request: KibaApiRequest[ExampleRequest]) -> str:
        return request.data.value

    @with_request_context(contextHolder=holder, contextFactory=context_factory)
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> str:
        return holder.get_value() or ''

    assert await endpoint(_request()) == 'value'
    assert holder.get_value() is None


@pytest.mark.asyncio
async def test_with_request_context_restores_context_after_stream_consumption() -> None:
    holder = ContextSettableValueHolder[str | None](defaultValue=None)

    async def context_factory(request: KibaApiRequest[ExampleRequest]) -> str:
        return request.data.value

    @with_request_context(contextHolder=holder, contextFactory=context_factory)
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> AsyncIterator[str]:
        yield holder.get_value() or ''

    result = await endpoint(_request())
    assert holder.get_value() == 'value'
    assert [item async for item in result] == ['value']
    assert holder.get_value() is None
