from typing import Dict
from typing import TypeVar
from typing import Union

DictKeyType = TypeVar('DictKeyType')  # pylint: disable=invalid-name
DictValueType = TypeVar('DictValueType')  # pylint: disable=invalid-name
DictValueType2 = TypeVar('DictValueType2')  # pylint: disable=invalid-name

def merge_dicts(dict1: Dict[DictKeyType, DictValueType], dict2: Dict[DictKeyType, DictValueType2]) -> Dict[DictKeyType, Union[DictValueType, DictValueType2]]:
    return {**dict1, **dict2}
