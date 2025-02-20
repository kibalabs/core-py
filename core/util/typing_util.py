from collections.abc import Mapping
from typing import Any
from typing import Union

JsonBaseType = str | int | float | bool | None

JSON5 = JsonBaseType
JSON4 = Union[JsonBaseType, list[JSON5], Mapping[str, JSON5]]
JSON3 = Union[JsonBaseType, list[JSON4], Mapping[str, JSON4]]
JSON2 = Union[JsonBaseType, list[JSON3], Mapping[str, JSON3]]
JSON1 = Union[JsonBaseType, list[JSON2], Mapping[str, JSON2]]
JSON = Union[JsonBaseType, list[JSON1], Mapping[str, JSON1]]
UnsafeJSON5 = Union[JsonBaseType, list[Any], Mapping[str, Any]]  # type: ignore[explicit-any]
UnsafeJSON4 = Union[JsonBaseType, list[UnsafeJSON5], Mapping[str, UnsafeJSON5]]
UnsafeJSON3 = Union[JsonBaseType, list[UnsafeJSON4], Mapping[str, UnsafeJSON4]]
UnsafeJSON2 = Union[JsonBaseType, list[UnsafeJSON3], Mapping[str, UnsafeJSON3]]
UnsafeJSON1 = Union[JsonBaseType, list[UnsafeJSON2], Mapping[str, UnsafeJSON2]]
UnsafeJSON = Union[JsonBaseType, list[UnsafeJSON1], Mapping[str, UnsafeJSON1]]

# NOTE(krishan711): copied from https://github.com/python/typing/issues/182
# NOTE(krishan711): this doesn't work great with pydantic yet due to: https://github.com/pydantic/pydantic/issues/7111
# NOTE(krishan711): Json: TypeAlias = dict[str, "Json"] | Mapping[str, "Json"] | list["Json"] | Sequence["Json"] | JsonBaseType
Json = JSON
JsonDict = dict[str, Json]
JsonList = list[Json]
