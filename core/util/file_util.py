import os
import pathlib
import shutil
from typing import Optional

import aiofiles
import aiofiles.os

KILOBYTE = 1024
MEGABYTE = KILOBYTE * 1024

CACHE_CONTROL_TEMPORARY_FILE = 'public,max-age=1'
CACHE_CONTROL_FINAL_FILE = 'public,max-age=31536000'

async def remove_file(filePath: str) -> None:
    await aiofiles.os.remove(filePath)

async def remove_directory(directory: str) -> None:
    shutil.rmtree(directory)
    # TODO(krish): fix this to be async, command below doesn't work if the directory is not empty
    # await aiofiles.os.rmdir(directory)

def remove_file_sync(filePath: str) -> None:
    os.remove(filePath)

def remove_directory_sync(directory: str) -> None:
    shutil.rmtree(directory)

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

async def write_file(filePath: str, content: str, shouldRaiseIfFileExists: Optional[bool] = False) -> None:
    async with aiofiles.open(filePath, 'x' if shouldRaiseIfFileExists else 'w') as file:
        await file.write(content)

async def write_file_bytes(filePath: str, content: bytes, shouldRaiseIfFileExists: Optional[bool] = False) -> None:
    async with aiofiles.open(filePath, 'xb' if shouldRaiseIfFileExists else 'wb') as file:
        await file.write(content)

def write_file_sync(filePath: str, content: str, shouldRaiseIfFileExists: Optional[bool] = False) -> None:
    with open(filePath, 'x' if shouldRaiseIfFileExists else 'w') as file:
        file.write(content)

def write_file_bytes_sync(filePath: str, content: bytes, shouldRaiseIfFileExists: Optional[bool] = False) -> None:
    with open(filePath, 'xb' if shouldRaiseIfFileExists else 'wb') as file:
        file.write(content)

async def create_directory(directory: str, shouldAllowExisting: bool = True) -> None:
    pathlib.Path(directory).mkdir(parents=True, exist_ok=shouldAllowExisting)

async def create_directory_sync(directory: str, shouldAllowExisting: bool = True) -> None:
    pathlib.Path(directory).mkdir(parents=True, exist_ok=shouldAllowExisting)
