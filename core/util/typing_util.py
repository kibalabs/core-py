from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import TypeAlias
from typing import Union

JsonBaseType = str | int | float | bool | None

JSON5 = JsonBaseType
JSON4 = Union[JsonBaseType, List[JSON5], Mapping[str, JSON5]]
JSON3 = Union[JsonBaseType, List[JSON4], Mapping[str, JSON4]]
JSON2 = Union[JsonBaseType, List[JSON3], Mapping[str, JSON3]]
JSON1 = Union[JsonBaseType, List[JSON2], Mapping[str, JSON2]]
JSON = Union[JsonBaseType, List[JSON1], Mapping[str, JSON1]]  # pylint: disable=invalid-name
UnsafeJSON5 = Union[JsonBaseType, List[Any], Mapping[str, Any]]  # type: ignore  # pylint: disable=invalid-name
UnsafeJSON4 = Union[JsonBaseType, List[UnsafeJSON5], Mapping[str, UnsafeJSON5]]  # pylint: disable=invalid-name
UnsafeJSON3 = Union[JsonBaseType, List[UnsafeJSON4], Mapping[str, UnsafeJSON4]]  # pylint: disable=invalid-name
UnsafeJSON2 = Union[JsonBaseType, List[UnsafeJSON3], Mapping[str, UnsafeJSON3]]  # pylint: disable=invalid-name
UnsafeJSON1 = Union[JsonBaseType, List[UnsafeJSON2], Mapping[str, UnsafeJSON2]]  # pylint: disable=invalid-name
UnsafeJSON = Union[JsonBaseType, List[UnsafeJSON1], Mapping[str, UnsafeJSON1]]  # pylint: disable=invalid-name

# NOTE(krishan711): copied from https://github.com/python/typing/issues/182
# NOTE(krishan711): this doesn't work great with pydantic yet due to: https://github.com/pydantic/pydantic/issues/7111
# Json: TypeAlias = Dict[str, "Json"] | Mapping[str, "Json"] | List["Json"] | Sequence["Json"] | JsonBaseType
Json = JSON
JsonDict: TypeAlias = Dict[str, Json]
JsonList: TypeAlias = List[Json]
