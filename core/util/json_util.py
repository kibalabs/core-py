from typing import Any

import orjson
import json

from core import logging
from core.exceptions import KibaException
from core.util.typing_util import Json


class JsonDecodeException(KibaException):
    pass


class JsonEncodeException(KibaException):
    pass

_HAS_LOGGED_FOR_SERIALIZATION_ERROR = False

def dumpb(obj: Any) -> bytes:  # type: ignore[explicit-any]
    global _HAS_LOGGED_FOR_SERIALIZATION_ERROR
    try:
        return orjson.dumps(obj)
    except TypeError as exception:
        if str(exception) == "Integer exceeds 64-bit range":
            if not _HAS_LOGGED_FOR_SERIALIZATION_ERROR:
                logging.warning(f"There was an error during the serialization an object: `{exception}`, falling back to json.")
                _HAS_LOGGED_FOR_SERIALIZATION_ERROR = True
            return json.dumps(obj).encode("utf-8")
        raise JsonEncodeException(message=str(exception)) from exception
    except orjson.JSONEncodeError as exception:
        raise JsonEncodeException(message=str(exception)) from exception


def dumps(obj: Any) -> str:  # type: ignore[explicit-any]
    return dumpb(obj=obj).decode('utf-8')


def loads(json: str | bytes | bytearray) -> Json:
    try:
        return orjson.loads(json)  # type: ignore[no-any-return]
    except orjson.JSONDecodeError as exception:
        raise JsonDecodeException(message=str(exception)) from exception
