import datetime
import pytest

from core.caching.dict_cache import DictCache
from core.util import date_util


class TestDictCache:

    @pytest.fixture
    def cache(self) -> DictCache:
        return DictCache()

    async def test_set_and_get(self, cache: DictCache):
        key = "test_key"
        value = "test_value"
        success = await cache.set(key=key, value=value, expirySeconds=60)
        assert success is True
        result = await cache.get(key=key)
        assert result == value

    async def test_get_nonexistent_key(self, cache: DictCache):
        result = await cache.get(key="nonexistent")
        assert result is None

    async def test_delete_existing_key(self, cache: DictCache):
        key = "test_key"
        value = "test_value"
        await cache.set(key=key, value=value, expirySeconds=60)
        success = await cache.delete(key=key)
        assert success is True
        result = await cache.get(key=key)
        assert result is None

    async def test_delete_nonexistent_key(self, cache: DictCache):
        success = await cache.delete(key="nonexistent")
        assert success is False

    async def test_expiry(self, cache: DictCache, monkeypatch):
        key = "test_key"
        value = "test_value"
        await cache.set(key=key, value=value, expirySeconds=60)

        # Mock the current time to be after expiry
        future_time = date_util.datetime_from_now(seconds=61)
        monkeypatch.setattr(date_util, "datetime_from_now", lambda: future_time)

        result = await cache.get(key=key)
        assert result is None

    async def test_overwrite_existing_key(self, cache: DictCache):
        key = "test_key"
        value1 = "test_value_1"
        value2 = "test_value_2"
        await cache.set(key=key, value=value1, expirySeconds=60)
        await cache.set(key=key, value=value2, expirySeconds=60)
        result = await cache.get(key=key)
        assert result == value2

    def test_can_store_complex_objects(self, cache: DictCache):
        assert cache.can_store_complex_objects() is True

    def test_is_private_flag(self):
        private_cache = DictCache(isPrivate=True)
        assert private_cache.isPrivate is True
        public_cache = DictCache(isPrivate=False)
        assert public_cache.isPrivate is False
