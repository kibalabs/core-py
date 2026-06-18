from __future__ import annotations

from pydantic import BaseModel

from core import logging
from core.caching.cache import Cache
from core.http import RestMethod

# from core.http.headers import CacheUsedHeader
# from core.http.headers import Header
# from core.model.protobuf import CacheEntryProto
# from core.requesters import KibaRequest
from core.requester.request import KibaRequest
from core.requester.response import KibaResponse
from core.util import date_util
from core.util import http_util
from core.util import url_util

_DEFAULT_MAX_AGE = 24 * 60 * 60


class RequesterCache:
    class CacheEntry(BaseModel):
        requestMethod: str
        requestUrl: str
        requestHeaders: dict[str, str]
        response: KibaResponse

        @property
        def expirySeconds(self) -> int:  # noqa: N802
            cacheControlHeader = self.response.headers['cacheControl']
            if not cacheControlHeader:  # or cacheControlHeader.ignoreCache:
                return 0
            expiryDate = date_util.datetime_from_datetime(dt=self.response.date, seconds=cacheControlHeader.maxAge or _DEFAULT_MAX_AGE)
            timeDifference = expiryDate - date_util.datetime_from_now()
            return timeDifference.seconds + (timeDifference.days * 60 * 60 * 24)

        def matches(self, request: KibaRequest) -> bool:
            if self.requestMethod != request.method or self.requestUrl != request.url:
                return False
            for varyHeaderName in self.response.headers['vary']:
                oldRequestValue = self.requestHeaders.get(varyHeaderName, '')
                oldRequestValues = [value.strip() for value in oldRequestValue.split(',')]
                newRequestValue = request.headers.get(varyHeaderName, '')
                newRequestValues = [value.strip() for value in newRequestValue.split(',')]
                if set(oldRequestValues) != set(newRequestValues):
                    return False
            return True

        @classmethod
        def create(cls, request: KibaRequest, response: KibaResponse, allowPrivate: bool = False) -> RequesterCache.CacheEntry | None:  # noqa: ARG003
            if request.method != RestMethod.GET:
                return None
            if response.status not in http_util.CACHABLE_STATUS_CODES:
                return None
            cacheControlHeader = response.headers.get('cacheControl')
            if cacheControlHeader is None:
                return None
            # if cacheControlHeader.ignoreCache or not cacheControlHeader.isPublic and not allowPrivate:
            #     return None
            return cls(
                requestMethod=request.method,
                requestUrl=str(request.url),
                requestHeaders=dict(request.headers),
                response=response,
            )

    def __init__(self, cache: Cache) -> None:
        self._cache = cache

    @staticmethod
    def _get_key(url: str) -> str:
        return url_util.encode_url(url=url)

    async def add(self, request: KibaRequest, response: KibaResponse) -> None:
        cacheEntry = RequesterCache.CacheEntry.create(request=request, response=response, allowPrivate=self._cache.isPrivate)
        if cacheEntry:
            cacheKey = self._get_key(url=str(request.url))
            cacheValue = cacheEntry.model_dump_json()
            try:
                await self._cache.set(key=cacheKey, value=cacheValue, expirySeconds=cacheEntry.expirySeconds)
            except Exception as exception:  # noqa: BLE001
                logging.error(msg=f'Caught error setting to cache: {self._cache.__class__.__name__!r}: {exception}')

    async def get(self, request: KibaRequest) -> KibaResponse | None:
        cacheControlHeader = request.headers['cacheControl']
        if not cacheControlHeader:  # cacheControlHeader.ignoreCache
            return None
        cacheKey = self._get_key(url=str(request.url))
        response = None
        try:
            responseData = await self._cache.get(key=cacheKey)
        except Exception as exception:  # noqa: BLE001
            logging.error(msg=f'Caught error retrieving from cache: {self._cache.__class__.__name__!r}: {exception}')
            responseData = None
        if responseData is not None:
            cacheEntry = RequesterCache.CacheEntry.model_validate_json(responseData)
            if cacheEntry.matches(request=request):
                response = cacheEntry.response
                response.headers['X-Cache-Used'] = 'RequesterCache-Hit'
        return response
