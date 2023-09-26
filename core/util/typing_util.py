from typing import Dict
from typing import Mapping
from typing import List
from typing import Any
from typing import TypeAlias
from typing import Union

JsonBaseType = str | int | float | bool | None
# NOTE(krishan711): this doesnt work great with pydantic yet due to: https://github.com/pydantic/pydantic/issues/7111
# NOTE(krishan711): copied from https://github.com/python/typing/issues/182
# Json: TypeAlias = Dict[str, "Json"] | Mapping[str, "Json"] | List["Json"] | Sequence["Json"] | JsonBaseType
# JsonDict: TypeAlias = Dict[str, Json]
# JsonList: TypeAlias = List[Json]
# NOTE(krishan711): this is temporary whilst the above doesnt work
JSON5 = JsonBaseType
JSON4 = Union[JsonBaseType, List[JSON5], Mapping[str, JSON5]]
JSON3 = Union[JsonBaseType, List[JSON4], Mapping[str, JSON4]]
JSON2 = Union[JsonBaseType, List[JSON3], Mapping[str, JSON3]]
JSON1 = Union[JsonBaseType, List[JSON2], Mapping[str, JSON2]]
Json = Union[JsonBaseType, List[JSON1], Mapping[str, JSON1]]
UnsafeJSON5 = Union[JsonBaseType, List[Any], Mapping[str, Any]]  # type: ignore
UnsafeJSON4 = Union[JsonBaseType, List[UnsafeJSON5], Mapping[str, UnsafeJSON5]]
UnsafeJSON3 = Union[JsonBaseType, List[UnsafeJSON4], Mapping[str, UnsafeJSON4]]
UnsafeJSON2 = Union[JsonBaseType, List[UnsafeJSON3], Mapping[str, UnsafeJSON3]]
UnsafeJSON1 = Union[JsonBaseType, List[UnsafeJSON2], Mapping[str, UnsafeJSON2]]
UnsafeJSON = Union[JsonBaseType, List[UnsafeJSON1], Mapping[str, UnsafeJSON1]]
JsonDict: TypeAlias = Dict[str, Json]
JsonList: TypeAlias = List[Json]

# TODO(krishan711): remove this in the next major version
JSON = Json
