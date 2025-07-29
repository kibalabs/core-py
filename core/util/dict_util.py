def merge_dicts[DictKeyType, DictValueType, DictValueType2](dict1: dict[DictKeyType, DictValueType], dict2: dict[DictKeyType, DictValueType2]) -> dict[DictKeyType, DictValueType | DictValueType2]:
    return {**dict1, **dict2}
