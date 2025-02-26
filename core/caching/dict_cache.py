from __future__ import annotations

import dataclasses
import datetime
from collections.abc import MutableMapping

from core.caching.cache import Cache
from core.util import date_util


class DictCache(Cache):
    @dataclasses.dataclass
    class CacheEntry:
        value: str
        expiryDate: datetime.datetime

    def __init__(self, isPrivate: bool = False) -> None:
        super().__init__(isPrivate=isPrivate)
        self._entries: MutableMapping[str, DictCache.CacheEntry] = {}

    async def set(self, key: str, value: str, expirySeconds: float) -> bool:
        self._entries[key] = DictCache.CacheEntry(
            value=value,
            expiryDate=date_util.datetime_from_now(seconds=expirySeconds),
        )
        return True

    def _internal_get(self, key: str) -> str | None:
        entry = self._entries.get(key)
        if not entry:
            return None
        if entry.expiryDate < date_util.datetime_from_now():
            del self._entries[key]
            return None
        return entry.value

    async def get(self, key: str) -> str | None:
        return self._internal_get(key=key)

    async def delete(self, key: str) -> bool:
        ret = self._internal_get(key=key)
        if ret:
            del self._entries[key]
        return ret is not None

    def can_store_complex_objects(self) -> bool:  # pylint: disable=no-self-use
        return True
