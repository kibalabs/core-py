from typing import Dict
from typing import Mapping
from typing import List
from typing import Sequence
from typing import TypeAlias

# NOTE(krishan711): copied from https://github.com/python/typing/issues/182
JsonBaseType = str | int | float | bool | None
Json: TypeAlias = Dict[str, "Json"] | Mapping[str, "Json"] | List["Json"] | Sequence["Json"] | JsonBaseType
JsonDict: TypeAlias = Dict[str, Json]
JsonList: TypeAlias = List[Json]

# TODO(krishan711): remove this in the next major version
JSON = Json
