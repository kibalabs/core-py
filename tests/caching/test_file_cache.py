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
