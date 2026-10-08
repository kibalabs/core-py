import enum
import typing
from collections.abc import Mapping
from collections.abc import Sequence

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

JsonBaseType = str | int | float | bool | None
type Json = dict[str, 'Json'] | Mapping[str, 'Json'] | list['Json'] | Sequence['Json'] | JsonBaseType
type JsonObject = dict[str, 'Json']
type JsonList = list['Json']


class Undefined(enum.Enum):
    UNDEFINED = 'UNDEFINED'

    def __repr__(self) -> str:
        return 'UNDEFINED'

    @classmethod
    def __get_pydantic_core_schema__(cls, sourceType: typing.Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:  # type: ignore[explicit-any]
        # NOTE(krishan711): only the default can be UNDEFINED, input values (e.g. "UNDEFINED" in json) must never validate to it
        return core_schema.is_instance_schema(cls)


UNDEFINED: typing.Final = Undefined.UNDEFINED
type UpdateValue[T] = T | Undefined
