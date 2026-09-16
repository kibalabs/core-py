import typing
from typing import Any

import orjson
import pydantic_core

from core import logging
from core.exceptions import KibaException
from core.util.typing_util import Json


class JsonDecodeException(KibaException):
    pass


class JsonEncodeException(KibaException):
    pass


_HAS_LOGGED_FOR_SERIALIZATION_ERROR = False


def dumpb(obj: Any) -> bytes:  # type: ignore[explicit-any]
    global _HAS_LOGGED_FOR_SERIALIZATION_ERROR  # noqa: PLW0603
    try:
        # NOTE(krishan711): Keep UTC datetime output aligned with pydantic's ISO 8601 format.
        return orjson.dumps(obj, option=orjson.OPT_UTC_Z)
    except TypeError as exception:
        if str(exception) == 'Integer exceeds 64-bit range':
            if not _HAS_LOGGED_FOR_SERIALIZATION_ERROR:
                logging.warning(f'There was an error during the serialization an object: `{exception}`, falling back to pydantic.')
                _HAS_LOGGED_FOR_SERIALIZATION_ERROR = True
            # NOTE(krishan711): orjson is faster, but doesnt support ints bigger than 64bit
            # so we use pydantic instead (still faster than python json)
            return pydantic_core.to_json(obj, fallback=str, inf_nan_mode='null')
        raise JsonEncodeException(message=str(exception)) from exception


def dumps(obj: Any) -> str:  # type: ignore[explicit-any]
    return dumpb(obj=obj).decode('utf-8')


def loads(json: str | bytes | bytearray) -> Json:
    try:
        # NOTE(krishan711): orjson is faster, but doesnt support ints bigger than 64bit
        # so we use pydantic instead (still faster than python json)
        return typing.cast(Json, pydantic_core.from_json(json, allow_inf_nan=False))
    except ValueError as exception:
        raise JsonDecodeException(message=str(exception)) from exception
