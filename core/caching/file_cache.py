from __future__ import annotations

import asyncio
import os

from core.caching.cache import Cache
from core.util import date_util
from core.util import file_util


class FileCache(Cache):
    def __init__(self, cacheDirectory: str, isPrivate: bool = False) -> None:
        super().__init__(isPrivate=isPrivate)
        self._cacheDirectory = cacheDirectory

    async def set(self, key: str, value: str, expirySeconds: float) -> bool:
        cacheFileDirectory = os.path.join(self._cacheDirectory, key)
        contentFilePath = os.path.join(cacheFileDirectory, 'content.txt')
        expiryFilePath = os.path.join(cacheFileDirectory, 'expiryDate.txt')
        expiryDateString = date_util.datetime_to_string(dt=date_util.datetime_from_now(seconds=expirySeconds))
        await asyncio.gather(
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
        return await self._internal_get(key=key)

    async def delete(self, key: str) -> bool:
        # NOTE(krishan711): we only delete content file for speed
        cacheFileDirectory = os.path.join(self._cacheDirectory, key)
        contentFilePath = os.path.join(cacheFileDirectory, 'content.txt')
        fileExists = await file_util.file_exists(filePath=contentFilePath)
        if fileExists:
            await file_util.remove_file(filePath=contentFilePath)
        return fileExists

    def can_store_complex_objects(self) -> bool:
        return False
