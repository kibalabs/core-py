import pytest
from starlette.responses import StreamingResponse

from core.api.request_context import RequestContext
from core.api.request_context import RequestContextHolder
from core.api.request_context import RequestContextMiddleware
from core.api.request_context import create_request_context


@pytest.mark.asyncio
async def test_request_context_middleware_provides_origin_ip() -> None:
    holder = RequestContextHolder[RequestContext]()
    observedContext: list[RequestContext] = []

    async def app(scope: dict[str, object], receive: object, send: object) -> None:
        del scope, receive, send
        observedContext.append(holder.get_value())

    middleware = RequestContextMiddleware(app, requestContextHolder=holder, requestContextFactory=create_request_context)
    await middleware(scope={'type': 'http', 'originIp': '203.0.113.1'}, receive=None, send=None)

    assert observedContext == [RequestContext(originIp='203.0.113.1')]
    with pytest.raises(RuntimeError, match='No request context is active'):
        holder.get_value()


@pytest.mark.asyncio
async def test_request_context_remains_active_until_stream_consumption() -> None:
    holder = RequestContextHolder[RequestContext]()
    observedOriginIps: list[str | None] = []
    messages: list[dict[str, object]] = []

    async def app(scope: dict[str, object], receive: object, send: object) -> None:
        async def content() -> object:
            observedOriginIps.append(holder.get_value().originIp)
            yield b'body'

        response = StreamingResponse(content())
        await response(scope, receive, send)

    async def receive() -> dict[str, object]:
        return {'type': 'http.disconnect'}

    async def send(message: dict[str, object]) -> None:
        messages.append(message)

    middleware = RequestContextMiddleware(app, requestContextHolder=holder, requestContextFactory=create_request_context)
    await middleware(scope={'type': 'http', 'originIp': '203.0.113.1'}, receive=receive, send=send)

    assert observedOriginIps == ['203.0.113.1']
    assert messages[-2] == {'type': 'http.response.body', 'body': b'body', 'more_body': True}
    with pytest.raises(RuntimeError, match='No request context is active'):
        holder.get_value()


def test_request_context_holder_restores_previous_context() -> None:
    holder = RequestContextHolder[RequestContext]()
    with holder.use_value(RequestContext(originIp='203.0.113.1')):
        assert holder.get_value().originIp == '203.0.113.1'
    with pytest.raises(RuntimeError, match='No request context is active'):
        holder.get_value()
