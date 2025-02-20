from typing import TypeVar
from typing import Union

DictKeyType = TypeVar('DictKeyType')  # pylint: disable=invalid-name
DictValueType = TypeVar('DictValueType')  # pylint: disable=invalid-name
DictValueType2 = TypeVar('DictValueType2')  # pylint: disable=invalid-name


def merge_dicts(dict1: dict[DictKeyType, DictValueType], dict2: dict[DictKeyType, DictValueType2]) -> dict[DictKeyType, Union[DictValueType, DictValueType2]]:
    return {**dict1, **dict2}
