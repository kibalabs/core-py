from collections.abc import Mapping
from collections.abc import Sequence

from pydantic.experimental.missing_sentinel import MISSING

JsonBaseType = str | int | float | bool | None
type Json = dict[str, 'Json'] | Mapping[str, 'Json'] | list['Json'] | Sequence['Json'] | JsonBaseType
type JsonObject = dict[str, 'Json']
type JsonList = list['Json']

UNDEFINED = MISSING
type UpdateValue[T] = T | MISSING  # type: ignore[valid-type]
