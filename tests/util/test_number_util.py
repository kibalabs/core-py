import pytest

from core.util import number_util


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        (0, '0.00'),
        (0.5, '0.50'),
        (1.25, '1.2'),
        (100, '100.0'),
        (101, '101'),
        (999, '999'),
        (1000, '1.0K'),
        (9999, '10.0K'),
        (10000, '10K'),
        (999999, '1000K'),
        (1000000, '1.0M'),
        (10000000, '10M'),
        (1000000000, '1B'),
        (2500000000, '2B'),
    ],
)
def test_short_format_number(value: float, expected: str) -> None:
    assert number_util.short_format_number(value) == expected
