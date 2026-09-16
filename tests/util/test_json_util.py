import datetime
import math

import pytest

from core.util import json_util


class TestJsonUtil:

    def test_dumps_with_none(self):
        assert json_util.dumps(None) == 'null'

    def test_dumps_with_boolean_true(self):
        assert json_util.dumps(True) == 'true'

    def test_dumps_with_boolean_false(self):
        assert json_util.dumps(False) == 'false'

    def test_dumps_with_integer(self):
        assert json_util.dumps(42) == '42'

    def test_dumps_with_float(self):
        assert json_util.dumps(3.14) == '3.14'

    def test_dumps_with_string(self):
        assert json_util.dumps("hello") == '"hello"'

    def test_dumps_with_list(self):
        assert json_util.dumps([1, 2, 3]) == '[1,2,3]'

    def test_dumps_with_dict(self):
        assert json_util.dumps({"key": "value"}) == '{"key":"value"}'

    def test_dumps_with_nested_dict(self):
        data = {
            "name": "test",
            "nested": {
                "a": True,
                "b": [4, 5, 6],
            }
        }
        result = json_util.dumps(data)
        assert json_util.loads(result) == data

    def test_dumps_with_newline(self):
        assert json_util.dumps("Hello\nWorld") == '"Hello\\nWorld"'

    def test_dumps_with_tab(self):
        assert json_util.dumps("Hello\tWorld") == '"Hello\\tWorld"'

    def test_dumps_with_unicode_emoji(self):
        assert json_util.dumps("Hello 🌍") == '"Hello 🌍"'

    def test_dumps_with_quotes(self):
        assert json_util.dumps('Hello "World"') == '"Hello \\"World\\""'

    def test_dumps_with_custom_class_raises_error(self):
        class TestClass:
            pass
        with pytest.raises(json_util.JsonEncodeException) as exceptionInfo:
            json_util.dumps(TestClass())
        assert exceptionInfo.value.message == "Type is not JSON serializable: TestClass"

    def test_dumps_with_complex_number_raises_error(self):
        with pytest.raises(json_util.JsonEncodeException):
            json_util.dumps(complex(1, 2))

    def test_loads_with_null(self):
        assert json_util.loads('null') is None

    def test_loads_with_boolean_true(self):
        assert json_util.loads('true') is True

    def test_loads_with_boolean_false(self):
        assert json_util.loads('false') is False

    def test_loads_with_integer(self):
        assert json_util.loads('42') == 42

    def test_loads_with_float(self):
        assert json_util.loads('3.14') == 3.14

    def test_loads_with_string(self):
        assert json_util.loads('"hello"') == "hello"

    def test_loads_with_list(self):
        assert json_util.loads('[1,2,3]') == [1, 2, 3]

    def test_loads_with_dict(self):
        assert json_util.loads('{"key":"value"}') == {"key": "value"}

    def test_loads_with_nested_dict(self):
        jsonStr = '{"name":"test","nested":{"a":true,"b":[4,5,6]}}'
        expected = {
            "name": "test",
            "nested": {
                "a": True,
                "b": [4, 5, 6],
            }
        }
        assert json_util.loads(jsonStr) == expected

    def test_loads_with_newline(self):
        assert json_util.loads('"Hello\\nWorld"') == "Hello\nWorld"

    def test_loads_with_tab(self):
        assert json_util.loads('"Hello\\tWorld"') == "Hello\tWorld"

    def test_loads_with_unicode_emoji(self):
        assert json_util.loads('"Hello 🌍"') == "Hello 🌍"

    def test_loads_with_quotes(self):
        assert json_util.loads('"Hello \\"World\\""') == 'Hello "World"'

    def test_loads_with_incomplete_object_raises_error(self):
        with pytest.raises(json_util.JsonDecodeException):
            json_util.loads('{')

    def test_loads_with_trailing_comma_raises_error(self):
        with pytest.raises(json_util.JsonDecodeException):
            json_util.loads('[1, 2,]')

    def test_loads_with_unquoted_string_raises_error(self):
        with pytest.raises(json_util.JsonDecodeException):
            json_util.loads('{"key": value}')

    def test_loads_with_undefined_raises_error(self):
        with pytest.raises(json_util.JsonDecodeException):
            json_util.loads('{"key": undefined}')

    def test_loads_with_single_quotes_raises_error(self):
        with pytest.raises(json_util.JsonDecodeException):
            json_util.loads("{'key': 'value'}")

    def test_loads_with_str_input(self):
        assert json_util.loads('{"key":"value"}') == {"key": "value"}

    def test_loads_with_bytes_input(self):
        assert json_util.loads(b'{"key":"value"}') == {"key": "value"}

    def test_loads_with_bytearray_input(self):
        assert json_util.loads(bytearray(b'{"key":"value"}')) == {"key": "value"}

    def test_loads_with_whitespace(self):
        jsonStr = '''
        {
            "a": 1,
            "b": 2
        }
        '''
        assert json_util.loads(jsonStr) == {"a": 1, "b": 2}

    def test_dumpb_with_very_long_integer(self):
        veryLongInteger = 11111111111111111111111
        result = json_util.dumpb(obj=veryLongInteger)
        assert isinstance(result, bytes)
        assert result == b'11111111111111111111111'

    def test_dumpb_and_loads_with_very_long_integer(self):
        veryLongInteger = 11111111111111111111111
        result = json_util.dumpb(obj=veryLongInteger)
        assert isinstance(result, bytes)
        assert int(json_util.loads(result)) == veryLongInteger

    def test_dumpb_with_very_long_integer_and_datetime(self):
        veryLongInteger = 25000000000000000001
        naiveDatetime = datetime.datetime.fromisoformat('2024-01-02T03:04:05.678901')
        utcDatetime = datetime.datetime(2024, 1, 2, 3, 4, 5, 678901, tzinfo=datetime.UTC)
        result = json_util.dumpb({
            'balance': veryLongInteger,
            'naive': naiveDatetime,
            'utc': utcDatetime,
        })
        assert result == b'{"balance":25000000000000000001,"naive":"2024-01-02T03:04:05.678901","utc":"2024-01-02T03:04:05.678901Z"}'

    def test_dumpb_with_very_long_integer_uses_pydantic_fallbacks(self):
        veryLongInteger = 25000000000000000001

        class TestObject:
            def __str__(self):
                return 'test-object'

        result = json_util.dumpb({
            'balance': veryLongInteger,
            'unknown': TestObject(),
            'not_a_number': math.nan,
        })
        assert result == b'{"balance":25000000000000000001,"unknown":"test-object","not_a_number":null}'

    def test_loads_preserves_large_integer_type_and_precision(self):
        value = 25000000000000000001
        decoded = json_util.loads(str(value))
        assert type(decoded) is int
        assert decoded == value

    def test_loads_preserves_nested_large_integer_type_and_precision(self):
        value = 25000000000000000001
        decoded = json_util.loads(f'{{"balance": {value}}}')
        assert type(decoded['balance']) is int
        assert decoded['balance'] == value
