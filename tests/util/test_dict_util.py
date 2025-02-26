from core.util import dict_util


class TestDictUtil:

    def test_merge_dicts_with_non_overlapping_keys(self):
        dict1 = {'a': 1, 'b': 2}
        dict2 = {'c': 3, 'd': 4}
        expected = {'a': 1, 'b': 2, 'c': 3, 'd': 4}
        result = dict_util.merge_dicts(dict1, dict2)
        assert result == expected

    def test_merge_dicts_with_overlapping_keys(self):
        dict1 = {'a': 1, 'b': 2}
        dict2 = {'b': 3, 'c': 4}
        expected = {'a': 1, 'b': 3, 'c': 4}  # dict2 values should override dict1 values
        result = dict_util.merge_dicts(dict1, dict2)
        assert result == expected

    def test_merge_dicts_with_empty_dicts(self):
        dict1: dict[str, int] = {}
        dict2: dict[str, int] = {}
        expected: dict[str, int] = {}
        result = dict_util.merge_dicts(dict1, dict2)
        assert result == expected

    def test_merge_dicts_with_one_empty_dict(self):
        dict1 = {'a': 1, 'b': 2}
        dict2: dict[str, int] = {}
        expected = {'a': 1, 'b': 2}
        result = dict_util.merge_dicts(dict1, dict2)
        assert result == expected

    def test_merge_dicts_with_different_value_types(self):
        dict1 = {'a': 1, 'b': 'string'}
        dict2 = {'c': True, 'd': 2.5}
        expected = {'a': 1, 'b': 'string', 'c': True, 'd': 2.5}
        result = dict_util.merge_dicts(dict1, dict2)
        assert result == expected
