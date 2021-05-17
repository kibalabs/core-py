from typing import Dict
from typing import Union
from typing import TypeVar

DictKeyType = TypeVar('DictKeyType')
DictValueType = TypeVar('DictValueType')
DictValueType2 = TypeVar('DictValueType2')

def merge_dicts(dict1: Dict[DictKeyType, DictValueType], dict2: Dict[DictKeyType, DictValueType2]) -> Dict[DictKeyType, Union[DictValueType, DictValueType2]]:
    return {**dict1, **dict2}
