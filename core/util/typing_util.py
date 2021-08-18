# NOTE(krishan711): waiting for JSON type to be defined in mypy: https://github.com/python/typing/issues/182
# NOTE(krishan711): copied from https://gist.github.com/BMDan/ede923f733dfdf5ed3f6c9634a3e281f
from typing import Any
from typing import List
from typing import Mapping
from typing import Union

JSONV = Union[str, int, float, bool, None]
JSON5 = JSONV
JSON4 = Union[JSONV, List[JSON5], Mapping[str, JSON5]]
JSON3 = Union[JSONV, List[JSON4], Mapping[str, JSON4]]
JSON2 = Union[JSONV, List[JSON3], Mapping[str, JSON3]]
JSON1 = Union[JSONV, List[JSON2], Mapping[str, JSON2]]
JSON = Union[JSONV, List[JSON1], Mapping[str, JSON1]]
UnsafeJSON5 = Union[JSONV, List[Any], Mapping[str, Any]]  # type: ignore
UnsafeJSON4 = Union[JSONV, List[UnsafeJSON5], Mapping[str, UnsafeJSON5]]
UnsafeJSON3 = Union[JSONV, List[UnsafeJSON4], Mapping[str, UnsafeJSON4]]
UnsafeJSON2 = Union[JSONV, List[UnsafeJSON3], Mapping[str, UnsafeJSON3]]
UnsafeJSON1 = Union[JSONV, List[UnsafeJSON2], Mapping[str, UnsafeJSON2]]
UnsafeJSON = Union[JSONV, List[UnsafeJSON1], Mapping[str, UnsafeJSON1]]
