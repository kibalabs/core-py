import datetime
import pytest

from core.exceptions import KibaException
from core.util import date_util


class TestDateUtil:

    def test_start_of_day_with_specific_datetime(self):
        test_dt = datetime.datetime(2025, 2, 26, 14, 30, 45, 123456, tzinfo=datetime.UTC)
        result = date_util.start_of_day(dt=test_dt)
        assert result.year == 2025
        assert result.month == 2
        assert result.day == 26
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.microsecond == 0
        assert result.tzinfo == datetime.UTC

    def test_start_of_day_with_none(self):
        result = date_util.start_of_day()
        now = datetime.datetime.now(tz=datetime.UTC)
        assert result.year == now.year
        assert result.month == now.month
        assert result.day == now.day
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.microsecond == 0
        assert result.tzinfo == datetime.UTC

    def test_end_of_day_with_specific_datetime(self):
        test_dt = datetime.datetime(2025, 2, 26, 14, 30, 45, 123456, tzinfo=datetime.UTC)
        result = date_util.end_of_day(dt=test_dt)
        assert result.year == 2025
        assert result.month == 2
        assert result.day == 26
        assert result.hour == 23
        assert result.minute == 59
        assert result.second == 59
        assert result.microsecond == 999999
        assert result.tzinfo == datetime.UTC

    def test_end_of_day_with_none(self):
        result = date_util.end_of_day()
        now = datetime.datetime.now(tz=datetime.UTC)
        assert result.year == now.year
        assert result.month == now.month
        assert result.day == now.day
        assert result.hour == 23
        assert result.minute == 59
        assert result.second == 59
        assert result.microsecond == 999999
        assert result.tzinfo == datetime.UTC

    def test_datetime_from_datetime_with_days(self):
        base_dt = datetime.datetime(2025, 2, 26, 14, 30, 45, 123456, tzinfo=datetime.UTC)
        result = date_util.datetime_from_datetime(dt=base_dt, days=1)
        assert result == base_dt + datetime.timedelta(days=1)

    def test_datetime_from_datetime_with_seconds(self):
        base_dt = datetime.datetime(2025, 2, 26, 14, 30, 45, 123456, tzinfo=datetime.UTC)
        result = date_util.datetime_from_datetime(dt=base_dt, seconds=30)
        assert result == base_dt + datetime.timedelta(seconds=30)

    def test_datetime_from_datetime_with_milliseconds(self):
        base_dt = datetime.datetime(2025, 2, 26, 14, 30, 45, 123456, tzinfo=datetime.UTC)
        result = date_util.datetime_from_datetime(dt=base_dt, milliseconds=500)
        assert result == base_dt + datetime.timedelta(milliseconds=500)

    def test_datetime_from_datetime_with_minutes(self):
        base_dt = datetime.datetime(2025, 2, 26, 14, 30, 45, 123456, tzinfo=datetime.UTC)
        result = date_util.datetime_from_datetime(dt=base_dt, minutes=15)
        assert result == base_dt + datetime.timedelta(minutes=15)

    def test_datetime_from_datetime_with_hours(self):
        base_dt = datetime.datetime(2025, 2, 26, 14, 30, 45, 123456, tzinfo=datetime.UTC)
        result = date_util.datetime_from_datetime(dt=base_dt, hours=2)
        assert result == base_dt + datetime.timedelta(hours=2)

    def test_datetime_from_datetime_with_weeks(self):
        base_dt = datetime.datetime(2025, 2, 26, 14, 30, 45, 123456, tzinfo=datetime.UTC)
        result = date_util.datetime_from_datetime(dt=base_dt, weeks=1)
        assert result == base_dt + datetime.timedelta(weeks=1)

    def test_datetime_from_datetime_with_multiple_parameters(self):
        base_dt = datetime.datetime(2025, 2, 26, 14, 30, 45, 123456, tzinfo=datetime.UTC)
        result = date_util.datetime_from_datetime(
            dt=base_dt,
            days=1,
            seconds=30,
            milliseconds=500,
            minutes=15,
            hours=2,
            weeks=1
        )
        expected = base_dt + datetime.timedelta(
            days=1,
            seconds=30,
            milliseconds=500,
            minutes=15,
            hours=2,
            weeks=1
        )
        assert result == expected

    def test_datetime_from_now_with_delta(self):
        before = datetime.datetime.now(tz=datetime.UTC)
        result = date_util.datetime_from_now(days=1, hours=2, minutes=30)
        after = datetime.datetime.now(tz=datetime.UTC)

        expected_delta = datetime.timedelta(days=1, hours=2, minutes=30)
        assert before + expected_delta <= result <= after + expected_delta

    def test_datetime_from_string_with_default_format(self):
        test_str = "2025-02-26T14:30:45.123456"
        result = date_util.datetime_from_string(dateString=test_str)
        assert result == datetime.datetime(2025, 2, 26, 14, 30, 45, 123456, tzinfo=datetime.UTC)

    def test_datetime_from_string_with_custom_format(self):
        test_str = "2025-02-26 14:30:45"
        result = date_util.datetime_from_string(dateString=test_str, dateFormat="%Y-%m-%d %H:%M:%S")
        assert result == datetime.datetime(2025, 2, 26, 14, 30, 45, tzinfo=datetime.UTC)

    def test_datetime_from_string_with_invalid_format(self):
        with pytest.raises(KibaException) as exc_info:
            date_util.datetime_from_string(dateString="invalid date")
        assert "Invalid dateString" in str(exc_info.value)

    def test_datetime_to_string_with_default_format(self):
        test_dt = datetime.datetime(2025, 2, 26, 14, 30, 45, 123456, tzinfo=datetime.UTC)
        result = date_util.datetime_to_string(dt=test_dt)
        assert result == "2025-02-26T14:30:45.123456"

    def test_datetime_to_string_with_custom_format(self):
        test_dt = datetime.datetime(2025, 2, 26, 14, 30, 45, 123456, tzinfo=datetime.UTC)
        result = date_util.datetime_to_string(dt=test_dt, dateFormat="%Y-%m-%d %H:%M:%S")
        assert result == "2025-02-26 14:30:45"

    def test_date_hour_from_datetime_with_specific_datetime(self):
        test_dt = datetime.datetime(2025, 2, 26, 14, 30, 45, 123456, tzinfo=datetime.UTC)
        result = date_util.date_hour_from_datetime(dt=test_dt)
        assert result.year == 2025
        assert result.month == 2
        assert result.day == 26
        assert result.hour == 14
        assert result.minute == 0
        assert result.second == 0
        assert result.microsecond == 0
        assert result.tzinfo == datetime.UTC

    def test_date_hour_from_datetime_with_none(self):
        result = date_util.date_hour_from_datetime()
        now = datetime.datetime.now(tz=datetime.UTC)
        assert result.year == now.year
        assert result.month == now.month
        assert result.day == now.day
        assert result.hour == now.hour
        assert result.minute == 0
        assert result.second == 0
        assert result.microsecond == 0
        assert result.tzinfo == datetime.UTC

    def test_generate_clock_hour_intervals_with_multiple_hours(self):
        start = datetime.datetime(2025, 2, 26, 14, 30, 0, tzinfo=datetime.UTC)
        end = datetime.datetime(2025, 2, 26, 16, 45, 0, tzinfo=datetime.UTC)
        intervals = list(date_util.generate_clock_hour_intervals(startDate=start, endDate=end))
        assert len(intervals) == 3
        assert intervals[0] == (start, datetime.datetime(2025, 2, 26, 15, 0, 0, tzinfo=datetime.UTC))
        assert intervals[1] == (
            datetime.datetime(2025, 2, 26, 15, 0, 0, tzinfo=datetime.UTC),
            datetime.datetime(2025, 2, 26, 16, 0, 0, tzinfo=datetime.UTC)
        )
        assert intervals[2] == (
            datetime.datetime(2025, 2, 26, 16, 0, 0, tzinfo=datetime.UTC),
            end
        )

    def test_generate_clock_hour_intervals_with_single_hour(self):
        start = datetime.datetime(2025, 2, 26, 14, 30, 0, tzinfo=datetime.UTC)
        end = datetime.datetime(2025, 2, 26, 14, 45, 0, tzinfo=datetime.UTC)
        intervals = list(date_util.generate_clock_hour_intervals(startDate=start, endDate=end))
        assert len(intervals) == 1
        assert intervals[0] == (start, end)

    def test_generate_hourly_intervals_with_multiple_hours(self):
        start = datetime.datetime(2025, 2, 26, 14, 30, 0, tzinfo=datetime.UTC)
        end = datetime.datetime(2025, 2, 26, 16, 45, 0, tzinfo=datetime.UTC)
        intervals = list(date_util.generate_hourly_intervals(startDate=start, endDate=end))
        assert len(intervals) == 3
        assert intervals[0] == (start, start + datetime.timedelta(hours=1))
        assert intervals[1] == (
            start + datetime.timedelta(hours=1),
            start + datetime.timedelta(hours=2)
        )
        assert intervals[2] == (
            start + datetime.timedelta(hours=2),
            end
        )

    def test_generate_hourly_intervals_with_single_hour(self):
        start = datetime.datetime(2025, 2, 26, 14, 30, 0, tzinfo=datetime.UTC)
        end = datetime.datetime(2025, 2, 26, 14, 45, 0, tzinfo=datetime.UTC)
        intervals = list(date_util.generate_hourly_intervals(startDate=start, endDate=end))
        assert len(intervals) == 1
        assert intervals[0] == (start, end)

    def test_generate_datetime_intervals_with_one_minute(self):
        start = datetime.datetime(2025, 2, 26, 14, 30, 0, tzinfo=datetime.UTC)
        end = datetime.datetime(2025, 2, 26, 14, 35, 0, tzinfo=datetime.UTC)
        intervals = list(date_util.generate_datetime_intervals(startDate=start, endDate=end, seconds=60))
        assert len(intervals) == 5
        for i, interval in enumerate(intervals):
            assert interval[0] == start + datetime.timedelta(minutes=i)
            assert interval[1] == min(start + datetime.timedelta(minutes=i+1), end)

    def test_generate_datetime_intervals_with_custom_seconds(self):
        start = datetime.datetime(2025, 2, 26, 14, 30, 0, tzinfo=datetime.UTC)
        end = datetime.datetime(2025, 2, 26, 14, 30, 10, tzinfo=datetime.UTC)
        intervals = list(date_util.generate_datetime_intervals(startDate=start, endDate=end, seconds=2))
        assert len(intervals) == 5
        for i, interval in enumerate(intervals):
            assert interval[0] == start + datetime.timedelta(seconds=i*2)
            assert interval[1] == min(start + datetime.timedelta(seconds=(i+1)*2), end)

    def test_generate_dates_in_range_with_default_parameters(self):
        start = datetime.date(2025, 2, 26)
        end = datetime.date(2025, 3, 1)
        dates = list(date_util.generate_dates_in_range(startDate=start, endDate=end))
        assert dates == [
            datetime.date(2025, 2, 26),
            datetime.date(2025, 2, 27),
            datetime.date(2025, 2, 28),
            datetime.date(2025, 3, 1),
        ]

    def test_generate_dates_in_range_with_custom_interval(self):
        start = datetime.date(2025, 2, 26)
        end = datetime.date(2025, 3, 1)
        dates = list(date_util.generate_dates_in_range(startDate=start, endDate=end, days=2))
        assert dates == [
            datetime.date(2025, 2, 26),
            datetime.date(2025, 2, 28),
        ]

    def test_generate_dates_in_range_without_end_date(self):
        start = datetime.date(2025, 2, 26)
        end = datetime.date(2025, 3, 1)
        dates = list(date_util.generate_dates_in_range(startDate=start, endDate=end, shouldIncludeEndDate=False))
        assert dates == [
            datetime.date(2025, 2, 26),
            datetime.date(2025, 2, 27),
            datetime.date(2025, 2, 28),
        ]

    def test_calculate_diff_days_with_positive_difference(self):
        start = datetime.datetime(2025, 2, 26, tzinfo=datetime.UTC)
        end = datetime.datetime(2025, 3, 1, tzinfo=datetime.UTC)
        assert date_util.calculate_diff_days(startDate=start, endDate=end) == 3

    def test_calculate_diff_days_with_negative_difference(self):
        start = datetime.datetime(2025, 3, 1, tzinfo=datetime.UTC)
        end = datetime.datetime(2025, 2, 26, tzinfo=datetime.UTC)
        assert date_util.calculate_diff_days(startDate=start, endDate=end) == -3

    def test_calculate_diff_years_with_whole_year(self):
        start = datetime.datetime(2025, 2, 26, tzinfo=datetime.UTC)
        end = datetime.datetime(2026, 2, 26, tzinfo=datetime.UTC)
        assert date_util.calculate_diff_years(startDate=start, endDate=end) == 1.0

    def test_calculate_diff_years_with_partial_year(self):
        start = datetime.datetime(2025, 2, 26, tzinfo=datetime.UTC)
        end = datetime.datetime(2026, 8, 26, tzinfo=datetime.UTC)
        assert date_util.calculate_diff_years(startDate=start, endDate=end) == 1.5

    def test_datetime_from_date_with_standard_date(self):
        test_date = datetime.date(2025, 2, 26)
        result = date_util.datetime_from_date(date=test_date)
        assert isinstance(result, datetime.datetime)
        assert result.year == 2025
        assert result.month == 2
        assert result.day == 26
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.microsecond == 0

    def test_datetime_from_date_with_leap_year(self):
        test_date = datetime.date(2024, 2, 29)
        result = date_util.datetime_from_date(date=test_date)
        assert result.year == 2024
        assert result.month == 2
        assert result.day == 29
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.microsecond == 0

    def test_datetime_to_utc_with_naive_datetime(self):
        dt = datetime.datetime(2025, 2, 26, 14, 30)
        result = date_util.datetime_to_utc(dt=dt)
        assert result == datetime.datetime(2025, 2, 26, 14, 30, tzinfo=datetime.UTC)

    def test_datetime_to_utc_with_utc_datetime(self):
        dt = datetime.datetime(2025, 2, 26, 14, 30, tzinfo=datetime.UTC)
        result = date_util.datetime_to_utc(dt=dt)
        assert result == dt

    def test_datetime_to_utc_with_non_utc_timezone(self):
        tz = datetime.timezone(datetime.timedelta(hours=2))
        dt = datetime.datetime(2025, 2, 26, 14, 30, tzinfo=tz)
        result = date_util.datetime_to_utc(dt=dt)
        assert result == datetime.datetime(2025, 2, 26, 12, 30, tzinfo=datetime.UTC)

    def test_datetime_to_utc_with_negative_offset_timezone(self):
        tz = datetime.timezone(datetime.timedelta(hours=-5))
        dt = datetime.datetime(2025, 2, 26, 14, 30, tzinfo=tz)
        result = date_util.datetime_to_utc(dt=dt)
        assert result == datetime.datetime(2025, 2, 26, 19, 30, tzinfo=datetime.UTC)

    def test_datetime_to_utc_naive_datetime_with_tzinfo(self):
        dt = datetime.datetime(2025, 2, 26, 14, 30, tzinfo=datetime.UTC)
        result = date_util.datetime_to_utc_naive_datetime(dt=dt)
        assert result == datetime.datetime(2025, 2, 26, 14, 30)
        assert result.tzinfo is None

    def test_datetime_to_utc_naive_datetime_with_non_utc_timezone(self):
        tz = datetime.timezone(datetime.timedelta(hours=2))
        dt = datetime.datetime(2025, 2, 26, 14, 30, tzinfo=tz)
        result = date_util.datetime_to_utc_naive_datetime(dt=dt)
        assert result == datetime.datetime(2025, 2, 26, 12, 30)
        assert result.tzinfo is None

    def test_datetime_to_utc_naive_datetime_with_naive_datetime(self):
        dt = datetime.datetime(2025, 2, 26, 14, 30)
        result = date_util.datetime_to_utc_naive_datetime(dt=dt)
        assert result == datetime.datetime(2025, 2, 26, 14, 30)
        assert result.tzinfo is None

    def test_date_from_date_with_positive_days(self):
        test_date = datetime.date(2025, 2, 26)
        result = date_util.date_from_date(date=test_date, days=5)
        assert result == datetime.date(2025, 3, 3)

    def test_date_from_date_with_negative_days(self):
        test_date = datetime.date(2025, 2, 26)
        result = date_util.date_from_date(date=test_date, days=-5)
        assert result == datetime.date(2025, 2, 21)

    def test_date_from_date_across_month_boundary(self):
        test_date = datetime.date(2025, 2, 26)
        result = date_util.date_from_date(date=test_date, days=10)
        assert result == datetime.date(2025, 3, 8)

    def test_date_from_date_across_year_boundary(self):
        test_date = datetime.date(2025, 12, 26)
        result = date_util.date_from_date(date=test_date, days=10)
        assert result == datetime.date(2026, 1, 5)
