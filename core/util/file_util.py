import os
import pathlib
import shutil
import time

import aiofiles
import aiofiles.os

KILOBYTE = 1024
MEGABYTE = KILOBYTE * 1024

CACHE_CONTROL_TEMPORARY_FILE = 'public,max-age=1'
CACHE_CONTROL_FINAL_FILE = 'public,max-age=31536000'


async def remove_file(filePath: str) -> None:
    await aiofiles.os.remove(filePath)


async def remove_directory(directory: str) -> None:
    # TODO(krish): fix this to be async, command below doesn't work if the directory is not empty
    shutil.rmtree(directory)


def remove_file_sync(filePath: str) -> None:
    os.remove(filePath)


def remove_directory_sync(directory: str) -> None:
    shutil.rmtree(directory)


async def file_exists(filePath: str) -> bool:
    return await aiofiles.os.path.exists(filePath)


def file_exists_sync(filePath: str) -> bool:
    return os.path.exists(filePath)


async def get_file_age_millis(filePath: str) -> int:
    # NOTE(krishan711): is there an async verison of this?
    return int((time.time() - os.path.getmtime(filePath)) * 1000)


def get_file_age_millis_sync(filePath: str) -> int:
    return int((time.time() - os.path.getmtime(filePath)) * 1000)


async def read_file(filePath: str) -> str:
    async with aiofiles.open(filePath, 'r') as file:
        return await file.read()


async def read_file_bytes(filePath: str) -> bytes:
    async with aiofiles.open(filePath, 'rb') as file:
        return await file.read()


def read_file_sync(filePath: str) -> str:
    with open(filePath, 'r') as file:
        return file.read()


def read_file_bytes_sync(filePath: str) -> bytes:
    with open(filePath, 'rb') as file:
        return file.read()


async def write_file(filePath: str, content: str, shouldRaiseIfFileExists: bool | None = False) -> None:
    async with aiofiles.open(filePath, 'x' if shouldRaiseIfFileExists else 'w') as file:
        await file.write(content)


async def write_file_bytes(filePath: str, content: bytes, shouldRaiseIfFileExists: bool | None = False) -> None:
    async with aiofiles.open(filePath, 'xb' if shouldRaiseIfFileExists else 'wb') as file:
        await file.write(content)


def write_file_sync(filePath: str, content: str, shouldRaiseIfFileExists: bool | None = False) -> None:
    with open(filePath, 'x' if shouldRaiseIfFileExists else 'w') as file:
        file.write(content)


def write_file_bytes_sync(filePath: str, content: bytes, shouldRaiseIfFileExists: bool | None = False) -> None:
    with open(filePath, 'xb' if shouldRaiseIfFileExists else 'wb') as file:
        file.write(content)


async def create_directory(directory: str, shouldAllowExisting: bool = True) -> None:
    pathlib.Path(directory).mkdir(parents=True, exist_ok=shouldAllowExisting)


async def create_directory_sync(directory: str, shouldAllowExisting: bool = True) -> None:
    pathlib.Path(directory).mkdir(parents=True, exist_ok=shouldAllowExisting)


def get_file_extension(filename: str) -> str:
    _, fileExtension = os.path.splitext(filename)
    return fileExtension
