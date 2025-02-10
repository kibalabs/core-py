from core.util import string_util


class TestStringUtil:

    def test_generate_random_string_default_characters(self):
        length = 10
        result = string_util.generate_random_string(length)
        assert len(result) == length
        assert all(c in string_util.CHARACTERS_ALPHANUMERIC for c in result)

    def test_generate_random_string_custom_characters(self):
        length = 5
        custom_chars = "ABC123"
        result = string_util.generate_random_string(length, custom_chars)
        assert len(result) == length
        assert all(c in custom_chars for c in result)

    def test_generate_random_string_zero_length(self):
        length = 0
        result = string_util.generate_random_string(length)
        assert result == ""

    def test_generate_random_string_single_character_set(self):
        length = 3
        single_char = "X"
        result = string_util.generate_random_string(length, single_char)
        assert result == "XXX"

    def test_generate_random_string_uniqueness(self):
        length = 20
        results = set(string_util.generate_random_string(length) for _ in range(5))
        assert len(results) > 1
