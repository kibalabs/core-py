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


async def remove_file(filePath: str, should_ignore_missing: bool = True) -> None:
    try:
        await aiofiles.os.remove(filePath)
    except FileNotFoundError:
        if not should_ignore_missing:
            raise


async def remove_directory(directory: str, should_ignore_missing: bool = True) -> None:
    try:
        # TODO(krish): fix this to be async, command below doesn't work if the directory is not empty
        shutil.rmtree(directory)
    except FileNotFoundError:
        if not should_ignore_missing:
            raise


def remove_file_sync(filePath: str, should_ignore_missing: bool = True) -> None:
    try:
        os.remove(filePath)
    except FileNotFoundError:
        if not should_ignore_missing:
            raise


def remove_directory_sync(directory: str, should_ignore_missing: bool = True) -> None:
    try:
        shutil.rmtree(directory)
    except FileNotFoundError:
        if not should_ignore_missing:
            raise


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


async def write_file(filePath: str, content: str, shouldCreateParentDirectories: bool = True, shouldRaiseIfFileExists: bool = False) -> None:
    if shouldCreateParentDirectories:
        await create_directory(directory=os.path.dirname(filePath), shouldAllowExisting=True)
    async with aiofiles.open(filePath, 'x' if shouldRaiseIfFileExists else 'w') as file:
        await file.write(content)


async def write_file_bytes(filePath: str, content: bytes, shouldCreateParentDirectories: bool = True, shouldRaiseIfFileExists: bool = False) -> None:
    if shouldCreateParentDirectories:
        await create_directory(directory=os.path.dirname(filePath), shouldAllowExisting=True)
    async with aiofiles.open(filePath, 'xb' if shouldRaiseIfFileExists else 'wb') as file:
        await file.write(content)


def write_file_sync(filePath: str, content: str, shouldCreateParentDirectories: bool = True, shouldRaiseIfFileExists: bool = False) -> None:
    if shouldCreateParentDirectories:
        create_directory_sync(directory=os.path.dirname(filePath), shouldAllowExisting=True)
    with open(filePath, 'x' if shouldRaiseIfFileExists else 'w') as file:
        file.write(content)


def write_file_bytes_sync(filePath: str, content: bytes, shouldCreateParentDirectories: bool = True, shouldRaiseIfFileExists: bool = False) -> None:
    if shouldCreateParentDirectories:
        create_directory_sync(directory=os.path.dirname(filePath), shouldAllowExisting=True)
    with open(filePath, 'xb' if shouldRaiseIfFileExists else 'wb') as file:
        file.write(content)


async def create_directory(directory: str, shouldAllowExisting: bool = True) -> None:
    pathlib.Path(directory).mkdir(parents=True, exist_ok=shouldAllowExisting)


def create_directory_sync(directory: str, shouldAllowExisting: bool = True) -> None:
    pathlib.Path(directory).mkdir(parents=True, exist_ok=shouldAllowExisting)


def get_file_extension(filename: str) -> str:
    _, fileExtension = os.path.splitext(filename)
    return fileExtension
