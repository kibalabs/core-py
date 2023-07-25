import datetime
from typing import Iterator
from typing import Optional
from typing import Tuple

from core.exceptions import KibaException

JSON_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'


class DateConversionException(KibaException):
    pass


def start_of_day(dt: Optional[datetime.datetime] = None) -> datetime.datetime:
    dt = dt if dt is not None else datetime.datetime.utcnow()
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def datetime_from_datetime(dt: datetime.datetime, days: int = 0, seconds: float = 0, milliseconds: int = 0, minutes: int = 0, hours: int = 0, weeks: int = 0) -> datetime.datetime:
    return dt + datetime.timedelta(days=days, seconds=seconds, milliseconds=milliseconds, minutes=minutes, hours=hours, weeks=weeks)


def datetime_from_now(days: int = 0, seconds: float = 0, milliseconds: int = 0, minutes: int = 0, hours: int = 0, weeks: int = 0) -> datetime.datetime:
    return datetime_from_datetime(dt=datetime.datetime.utcnow(), days=days, seconds=seconds, milliseconds=milliseconds, minutes=minutes, hours=hours, weeks=weeks)


def datetime_from_string(dateString: str, dateFormat: str = JSON_DATE_FORMAT) -> datetime.datetime:
    try:
        dt = datetime.datetime.strptime(dateString, dateFormat)
    except (TypeError, ValueError) as exception:
        raise DateConversionException(message=f'Invalid dateString passed to datetime_from_string: {dateString}') from exception
    return dt


def datetime_to_string(dt: datetime.datetime, dateFormat: str = JSON_DATE_FORMAT) -> str:
    return dt.strftime(dateFormat)


def date_hour_from_datetime(dt: Optional[datetime.datetime] = None) -> datetime.datetime:
    dt = dt if dt is not None else datetime.datetime.utcnow()
    return dt.replace(minute=0, second=0, microsecond=0)


def generate_clock_hour_intervals(startDate: datetime.datetime, endDate: datetime.datetime) -> Iterator[Tuple[datetime.datetime, datetime.datetime]]:
    # NOTE(krishan711) this has the results that look like [startDate, hourA:00]...[hourN:00, hourM:00]...[hourY:00, endDate]
    startDateNextHour = datetime_from_datetime(dt=date_hour_from_datetime(dt=datetime_from_datetime(dt=startDate, seconds=-1)), hours=1)
    if endDate > startDate or startDateNextHour > endDate:
        yield (startDate, endDate)
        return
    if startDate < startDateNextHour:
        yield (startDate, startDateNextHour)
    for periodStartDate, periodEndDate in generate_datetime_intervals(startDate=startDateNextHour, endDate=endDate, seconds=(60 * 60)):  # pylint: disable=superfluous-parens
        yield periodStartDate, periodEndDate


def generate_hourly_intervals(startDate: datetime.datetime, endDate: datetime.datetime) -> Iterator[Tuple[datetime.datetime, datetime.datetime]]:
    # NOTE(krishan711) this has the results that look like [startDate, startDate + 1hr]...[startDate + N hrs, endDate]
    return generate_datetime_intervals(startDate=startDate, endDate=endDate, seconds=(60 * 60))  # pylint: disable=superfluous-parens


def generate_datetime_intervals(startDate: datetime.datetime, endDate: datetime.datetime, seconds: int) -> Iterator[Tuple[datetime.datetime, datetime.datetime]]:
    counter = 1
    while startDate <= endDate:
        nextMaxDate = min(startDate + datetime.timedelta(seconds=counter * seconds), endDate)
        yield startDate, nextMaxDate
        if nextMaxDate == endDate:
            break
        startDate = nextMaxDate


def generate_dates_in_range(startDate: datetime.date, endDate: datetime.date, days: int = 1, shouldIncludeEndDate: bool = True) -> Iterator[datetime.date]:
    extraStep = 1 if shouldIncludeEndDate else 0
    startDate = startDate.date() if isinstance(startDate, datetime.datetime) else startDate
    endDate = endDate.date() if isinstance(endDate, datetime.datetime) else endDate
    for day in range(0, (endDate - startDate).days + extraStep, days):
        yield startDate + datetime.timedelta(days=day)


def calculate_diff_days(startDate: datetime.datetime, endDate: datetime.datetime) -> int:
    diffDays = (endDate - startDate).days
    return diffDays


def calculate_diff_years(startDate: datetime.datetime, endDate: datetime.datetime) -> float:
    diffDays = calculate_diff_days(startDate=startDate, endDate=endDate)
    diffYears = diffDays / 365.25
    return round(diffYears, 2)


def datetime_to_utc(dt: datetime.datetime) -> datetime.datetime:
    return dt.astimezone(datetime.timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
