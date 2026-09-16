import httpx2 as httpx
import pytest

from core.exceptions import NotFoundException
from core.exceptions import TooManyRequestsException
from core.requester.requester import Requester


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
