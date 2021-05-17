from typing import Any
from typing import Dict

def merge_dicts(dict1: Dict[Any, Any], dict2: Dict[Any, Any]) -> Dict:
    return {**dict1, **dict2}
