import httpx2 as httpx
import pytest

from core.exceptions import NotFoundException
from core.exceptions import TooManyRequestsException
from core.requester.requester import Requester
from core.requester.requester import RequesterTimeoutException


class TestRequesterExceptionHeaders:

    @pytest.mark.asyncio
    async def test_429_response_populates_retry_after_from_header(self):
        def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
            return httpx.Response(429, headers={'Retry-After': '17'}, text='Too Many Requests')

        requester = Requester()
        requester.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with pytest.raises(TooManyRequestsException) as excInfo:
            await requester.get(url='https://example.com/resource')
        assert excInfo.value.retryAfterSeconds == 17

    @pytest.mark.asyncio
    async def test_429_response_without_retry_after_header(self):
        def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
            return httpx.Response(429, text='Too Many Requests')

        requester = Requester()
        requester.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with pytest.raises(TooManyRequestsException) as excInfo:
            await requester.get(url='https://example.com/resource')
        assert excInfo.value.retryAfterSeconds is None

    @pytest.mark.asyncio
    async def test_404_response_still_maps_to_correct_exception_type(self):
        def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
            return httpx.Response(404, text='Not Found')

        requester = Requester()
        requester.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with pytest.raises(NotFoundException):
            await requester.get(url='https://example.com/resource')


class TestRequesterTimeouts:

    @pytest.mark.asyncio
    async def test_timeout_raises_requester_timeout_with_request_details(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout('', request=request)

        requester = Requester()
        requester.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with pytest.raises(RequesterTimeoutException) as excInfo:
            await requester.post(url='https://user:secret@example.com/v1/rpc?apiKey=secret', timeout=5)
        exception = excInfo.value
        assert (exception.method, exception.url, exception.timeoutSeconds, exception.timeoutType, exception.statusCode) == ('POST', 'https://example.com/v1/rpc', 5, 'ReadTimeout', 504)
        assert exception.message.startswith('POST https://example.com/v1/rpc timed out after ')
        assert 'secret' not in exception.message
        assert isinstance(exception.__cause__, httpx.ReadTimeout)
