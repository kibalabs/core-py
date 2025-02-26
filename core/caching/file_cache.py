from __future__ import annotations

import asyncio
import os
from threading import Lock

from core.caching.cache import Cache
from core.util import date_util
from core.util import file_util


class FileCache(Cache):
    def __init__(self, cacheDirectory: str, isPrivate: bool = False) -> None:
        super().__init__(isPrivate=isPrivate)
        self._cacheDirectory = cacheDirectory
        self._lock = Lock()

    # async def load_cache_file(
    #     fileName: str,
    #     expirySeconds: int = 3600,
    # ) -> str | None:
    #     cacheFileDirectory = os.path.join('./data/cache', fileName)
    #     fileExists = await file_util.file_exists(filePath=cacheFileDirectory)
    #     fileAgeMillis = await file_util.get_file_age_millis(filePath=cacheFileDirectory) if fileExists else 0
    #     if fileExists and (fileAgeMillis / 1000) < expirySeconds:
    #         return await file_util.read_file(filePath=cacheFileDirectory)
    #     return None

    # async def load_json_cache_file(  # type: ignore[explicit-any]
    #     fileName: str,
    #     expirySeconds: int = 3600,
    # ) -> dict[str, Any] | list[Any] | None:
    #     content = await load_cache_file(fileName=fileName, expirySeconds=expirySeconds)
    #     return json.loads(content) if content is not None else None

    async def set(self, key: str, value: str, expirySeconds: float) -> bool:
        cacheFileDirectory = os.path.join(self._cacheDirectory, key)
        contentFilePath = os.path.join(cacheFileDirectory, 'content.txt')
        expiryFilePath = os.path.join(cacheFileDirectory, 'expiryDate.txt')
        expiryDateString = date_util.datetime_to_string(dt=date_util.datetime_from_now(seconds=expirySeconds))
        with self._lock:
            asyncio.gather(
                *[
                    file_util.write_file(filePath=contentFilePath, content=value),
                    file_util.write_file(filePath=expiryFilePath, content=expiryDateString),
                ]
            )
            return True

    async def _internal_get(self, key: str) -> str | None:
        cacheFileDirectory = os.path.join(self._cacheDirectory, key)
        contentFilePath = os.path.join(cacheFileDirectory, 'content.txt')
        expiryFilePath = os.path.join(cacheFileDirectory, 'expiryDate.txt')
        contentFileExists = await file_util.file_exists(filePath=contentFilePath)
        if not contentFileExists:
            return None
        expiryFileExists = await file_util.file_exists(filePath=expiryFilePath)
        if not expiryFileExists:
            await file_util.remove_file(filePath=contentFilePath)
            return None
        expiryDateString = await file_util.read_file(filePath=expiryFilePath)
        expiryDate = date_util.datetime_from_string(dateString=expiryDateString)
        if expiryDate < date_util.datetime_from_now():
            await file_util.remove_file(filePath=contentFilePath)
            return None
        return await file_util.read_file(filePath=contentFilePath)

    async def get(self, key: str) -> str | None:
        with self._lock:
            return await self._internal_get(key=key)

    async def delete(self, key: str) -> bool:
        # NOTE(krishan711): we only delete content file for speed
        cacheFileDirectory = os.path.join(self._cacheDirectory, key)
        contentFilePath = os.path.join(cacheFileDirectory, 'content.txt')
        with self._lock:
            fileExists = await file_util.file_exists(filePath=contentFilePath)
            if fileExists:
                await file_util.remove_file(filePath=contentFilePath)
            return fileExists

    def can_store_complex_objects(self) -> bool:
        return False
