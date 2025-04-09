import datetime
from collections.abc import Iterator

from core.exceptions import KibaException

JSON_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'


class DateConversionException(KibaException):
    pass


def start_of_day(dt: datetime.datetime | None = None) -> datetime.datetime:
    dt = dt if dt is not None else datetime.datetime.now(tz=datetime.UTC)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(dt: datetime.datetime | None = None) -> datetime.datetime:
    dt = dt if dt is not None else datetime.datetime.now(tz=datetime.UTC)
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def datetime_from_datetime(dt: datetime.datetime, days: int = 0, seconds: float = 0, milliseconds: int = 0, minutes: int = 0, hours: int = 0, weeks: int = 0) -> datetime.datetime:
    return dt + datetime.timedelta(days=days, seconds=seconds, milliseconds=milliseconds, minutes=minutes, hours=hours, weeks=weeks)


def datetime_from_now(days: int = 0, seconds: float = 0, milliseconds: int = 0, minutes: int = 0, hours: int = 0, weeks: int = 0) -> datetime.datetime:
    return datetime_from_datetime(dt=datetime.datetime.now(tz=datetime.UTC), days=days, seconds=seconds, milliseconds=milliseconds, minutes=minutes, hours=hours, weeks=weeks)


def datetime_from_string(dateString: str, dateFormat: str = JSON_DATE_FORMAT) -> datetime.datetime:
    try:
        dt = datetime.datetime.strptime(dateString, dateFormat).replace(tzinfo=datetime.UTC)
    except (TypeError, ValueError) as exception:
        raise DateConversionException(message=f'Invalid dateString passed to datetime_from_string: {dateString}') from exception
    return dt


def datetime_to_string(dt: datetime.datetime, dateFormat: str = JSON_DATE_FORMAT) -> str:
    return dt.strftime(dateFormat)


def datetime_to_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.UTC)
    return dt.astimezone(datetime.UTC)


def date_hour_from_datetime(dt: datetime.datetime | None = None) -> datetime.datetime:
    dt = dt if dt is not None else datetime.datetime.now(tz=datetime.UTC)
    return dt.replace(minute=0, second=0, microsecond=0)


def generate_clock_hour_intervals(startDate: datetime.datetime, endDate: datetime.datetime) -> Iterator[tuple[datetime.datetime, datetime.datetime]]:
    # NOTE(krishan711) this has the results that look like [startDate, hourA:00]...[hourN:00, hourM:00]...[hourY:00, endDate]
    startDateNextHour = datetime_from_datetime(dt=date_hour_from_datetime(dt=datetime_from_datetime(dt=startDate, seconds=-1)), hours=1)
    if startDateNextHour > endDate:
        yield (startDate, endDate)
        return
    if startDate < startDateNextHour:
        yield (startDate, startDateNextHour)
    yield from generate_datetime_intervals(startDate=startDateNextHour, endDate=endDate, seconds=(60 * 60))


def generate_hourly_intervals(startDate: datetime.datetime, endDate: datetime.datetime) -> Iterator[tuple[datetime.datetime, datetime.datetime]]:
    # NOTE(krishan711) this has the results that look like [startDate, startDate + 1hr]...[startDate + N hrs, endDate]
    return generate_datetime_intervals(startDate=startDate, endDate=endDate, seconds=(60 * 60))


def generate_datetime_intervals(startDate: datetime.datetime, endDate: datetime.datetime, seconds: int) -> Iterator[tuple[datetime.datetime, datetime.datetime]]:
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
    years = endDate.year - startDate.year
    start_ordinal = startDate.replace(year=2000).toordinal()
    end_ordinal = endDate.replace(year=2000).toordinal()
    if end_ordinal < start_ordinal:
        years -= 1
        fraction = (end_ordinal + 365 - start_ordinal) / 365
    else:
        fraction = (end_ordinal - start_ordinal) / 365

    return round(years + fraction, 2)


def datetime_from_date(date: datetime.date) -> datetime.datetime:
    return datetime.datetime.combine(date=date, time=datetime.time.min, tzinfo=datetime.UTC)


def datetime_to_utc_naive_datetime(dt: datetime.datetime) -> datetime.datetime:
    utcDt = datetime_to_utc(dt=dt)
    return utcDt.replace(tzinfo=None)


def date_from_date(date: datetime.date, days: int) -> datetime.date:
    return date + datetime.timedelta(days=days)
