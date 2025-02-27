from typing import Any

import orjson

from core.exceptions import KibaException
from core.util.typing_util import Json


class JsonDecodeException(KibaException):
    pass


class JsonEncodeException(KibaException):
    pass


def dumps(obj: Any) -> str:  # type: ignore[explicit-any]
    try:
        return orjson.dumps(obj).decode('utf-8')
    except orjson.JSONEncodeError as exception:
        raise JsonEncodeException(message=str(exception)) from exception


def loads(json: str | bytes | bytearray) -> Json:
    try:
        return orjson.loads(json)  # type: ignore[no-any-return]
    except orjson.JSONDecodeError as exception:
        raise JsonDecodeException(message=str(exception)) from exception
