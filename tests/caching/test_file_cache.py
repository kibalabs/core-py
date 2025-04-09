import asyncio
import os
import tempfile
import shutil

import pytest

from core.caching.file_cache import FileCache
from core.util import date_util


class TestFileCache:

    @pytest.fixture
    def cache_dir(self):
        tempDirectory = tempfile.mkdtemp()
        yield tempDirectory
        shutil.rmtree(tempDirectory)

    @pytest.fixture
    def cache(self, cache_dir) -> FileCache:
        return FileCache(cacheDirectory=cache_dir)

    async def test_set_and_get(self, cache: FileCache):
        key = "test_key"
        value = "test_value"
        success = await cache.set(key=key, value=value, expirySeconds=60)
        assert success is True
        result = await cache.get(key=key)
        assert result == value

    async def test_get_nonexistent_key(self, cache: FileCache):
        result = await cache.get(key="nonexistent")
        assert result is None

    async def test_delete_existing_key(self, cache: FileCache):
        key = "test_key"
        value = "test_value"
        await cache.set(key=key, value=value, expirySeconds=60)
        success = await cache.delete(key=key)
        assert success is True
        result = await cache.get(key=key)
        assert result is None

    async def test_delete_nonexistent_key(self, cache: FileCache):
        success = await cache.delete(key="nonexistent")
        assert success is False

    async def test_expiry(self, cache: FileCache, monkeypatch):
        key = "test_key"
        value = "test_value"
        await cache.set(key=key, value=value, expirySeconds=60)
        future_time = date_util.datetime_from_now(seconds=61)
        monkeypatch.setattr(date_util, "datetime_from_now", lambda: future_time)
        result = await cache.get(key=key)
        assert result is None

    async def test_overwrite_existing_key(self, cache: FileCache):
        key = "test_key"
        value1 = "test_value_1"
        value2 = "test_value_2"
        await cache.set(key=key, value=value1, expirySeconds=60)
        await cache.set(key=key, value=value2, expirySeconds=60)
        result = await cache.get(key=key)
        assert result == value2

    def test_can_store_complex_objects(self, cache: FileCache):
        assert cache.can_store_complex_objects() is False

    def test_is_private_flag(self, cache_dir):
        private_cache = FileCache(cacheDirectory=cache_dir, isPrivate=True)
        assert private_cache.isPrivate is True
        public_cache = FileCache(cacheDirectory=cache_dir, isPrivate=False)
        assert public_cache.isPrivate is False

    async def test_file_structure(self, cache: FileCache, cache_dir):
        key = "test_key"
        value = "test_value"
        await cache.set(key=key, value=value, expirySeconds=60)
        cache_key_dir = os.path.join(cache_dir, key)
        content_file = os.path.join(cache_key_dir, 'content.txt')
        expiry_file = os.path.join(cache_key_dir, 'expiryDate.txt')
        assert os.path.exists(cache_key_dir)
        assert os.path.isfile(content_file)
        assert os.path.isfile(expiry_file)
        with open(content_file, 'r') as f:
            assert f.read() == value

    async def test_missing_expiry_file(self, cache: FileCache, cache_dir):
        key = "test_key"
        value = "test_value"
        await cache.set(key=key, value=value, expirySeconds=60)
        expiry_file = os.path.join(cache_dir, key, 'expiryDate.txt')
        os.remove(expiry_file)
        result = await cache.get(key=key)
        assert result is None
        content_file = os.path.join(cache_dir, key, 'content.txt')
        assert not os.path.exists(content_file)

    async def test_set_with_existing_directory(self, cache: FileCache, cache_dir):
        key = "existing_dir"
        os.makedirs(os.path.join(cache_dir, key), exist_ok=True)
        value = "test_value"
        success = await cache.set(key=key, value=value, expirySeconds=60)
        assert success is True
        result = await cache.get(key=key)
        assert result == value

    async def test_expired_content(self, cache: FileCache, cache_dir, monkeypatch):
        key = "expired_key"
        value = "test_value"
        await cache.set(key=key, value=value, expirySeconds=60)
        expiry_file = os.path.join(cache_dir, key, 'expiryDate.txt')
        past_time = date_util.datetime_to_string(dt=date_util.datetime_from_now(seconds=-10))
        with open(expiry_file, 'w') as f:
            f.write(past_time)
        result = await cache.get(key=key)
        assert result is None
        content_file = os.path.join(cache_dir, key, 'content.txt')
        assert not os.path.exists(content_file)
        assert not os.path.exists(expiry_file)

    async def test_malformed_expiry_file(self, cache: FileCache, cache_dir):
        key = "malformed_key"
        value = "test_value"
        await cache.set(key=key, value=value, expirySeconds=60)
        expiry_file = os.path.join(cache_dir, key, 'expiryDate.txt')
        with open(expiry_file, 'w') as f:
            f.write("invalid-date-format")
        result = await cache.get(key=key)
        assert result is None

    async def test_concurrent_operations(self, cache: FileCache):
        keys = [f"concurrent_key_{i}" for i in range(5)]
        values = [f"concurrent_value_{i}" for i in range(5)]
        tasks = [cache.set(key=keys[i], value=values[i], expirySeconds=60) for i in range(5)]
        results = await asyncio.gather(*tasks)
        assert all(results)
        get_tasks = [cache.get(key=keys[i]) for i in range(5)]
        get_results = await asyncio.gather(*get_tasks)
        assert get_results == values
        delete_tasks = [cache.delete(key=keys[i]) for i in range(5)]
        delete_results = await asyncio.gather(*delete_tasks)
        assert all(delete_results)

    async def test_internal_get_behavior(self, cache: FileCache, cache_dir):
        key = "internal_test"
        value = "internal_value"
        await cache.set(key=key, value=value, expirySeconds=60)
        internal_result = await cache._internal_get(key=key)
        regular_result = await cache.get(key=key)
        assert internal_result == regular_result == value
