from typing import TypeVar
from typing import Union

DictKeyType = TypeVar('DictKeyType')
DictValueType = TypeVar('DictValueType')
DictValueType2 = TypeVar('DictValueType2')


def merge_dicts(dict1: dict[DictKeyType, DictValueType], dict2: dict[DictKeyType, DictValueType2]) -> dict[DictKeyType, Union[DictValueType, DictValueType2]]:
    return {**dict1, **dict2}
