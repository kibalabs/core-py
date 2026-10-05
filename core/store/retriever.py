import dataclasses
import datetime
import typing
import uuid
from collections.abc import Sequence
from enum import Enum

import sqlalchemy
import sqlalchemy.sql.functions
from sqlalchemy.sql import ColumnElement
from sqlalchemy.sql import Select

from core.store.database import Database
from core.store.database import DatabaseTable
from core.store.database import ResultType
from core.util import date_util


class Direction(Enum):
    ASCENDING = 'ascending'
    DESCENDING = 'descending'


@dataclasses.dataclass
class Order:
    fieldName: str
    direction: Direction = Direction.DESCENDING


@dataclasses.dataclass
class RandomOrder(Order):
    fieldName: str = '__KIBA_RANDOM'


@dataclasses.dataclass
class FieldFilter:
    fieldName: str
    isNull: bool | None = None
    isNotNull: bool | None = None


@dataclasses.dataclass
class StringFieldFilter(FieldFilter):
    eq: str | None = None
    ne: str | None = None
    containedIn: Sequence[str] | None = None
    notContainedIn: Sequence[str] | None = None


@dataclasses.dataclass
class UUIDFieldFilter(FieldFilter):
    eq: uuid.UUID | str | None = None
    ne: uuid.UUID | str | None = None
    containedIn: Sequence[uuid.UUID | str] | None = None
    notContainedIn: Sequence[uuid.UUID | str] | None = None


@dataclasses.dataclass
class DateFieldFilter(FieldFilter):
    eq: datetime.datetime | None = None
    ne: datetime.datetime | None = None
    lte: datetime.datetime | None = None
    lt: datetime.datetime | None = None
    gte: datetime.datetime | None = None
    gt: datetime.datetime | None = None
    containedIn: Sequence[datetime.datetime] | None = None
    notContainedIn: Sequence[datetime.datetime] | None = None


@dataclasses.dataclass
class IntegerFieldFilter(FieldFilter):
    eq: int | None = None
    ne: int | None = None
    lte: int | None = None
    lt: int | None = None
    gte: int | None = None
    gt: int | None = None
    containedIn: Sequence[int] | None = None
    notContainedIn: Sequence[int] | None = None


@dataclasses.dataclass
class FloatFieldFilter(FieldFilter):
    eq: float | None = None
    ne: float | None = None
    lte: float | None = None
    lt: float | None = None
    gte: float | None = None
    gt: float | None = None
    containedIn: Sequence[float] | None = None
    notContainedIn: Sequence[float] | None = None


@dataclasses.dataclass
class BooleanFieldFilter(FieldFilter):
    eq: bool | None = None
    ne: bool | None = None


def uuid_from_value(value: uuid.UUID | str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(hex=value)


def datetime_to_column_value(column: sqlalchemy.ColumnElement[typing.Any], dt: datetime.datetime) -> datetime.datetime:  # type: ignore[explicit-any]
    # NOTE(krishan711): columns without a timezone store naive utc datetimes, columns with one store aware utc datetimes
    if getattr(column.type, 'timezone', False):
        return date_util.datetime_to_utc(dt=dt)
    return date_util.datetime_to_utc_naive_datetime(dt=dt)


def apply_order(query: Select[*ResultType], table: DatabaseTable, order: Order) -> Select[*ResultType]:
    if isinstance(order, RandomOrder):
        query = query.order_by(sqlalchemy.sql.functions.random())
    else:
        field = table.c[order.fieldName]
        query = query.order_by(field.asc() if order.direction == Direction.ASCENDING else field.desc())
    return query


def apply_orders(query: Select[*ResultType], table: DatabaseTable, orders: Sequence[Order]) -> Select[*ResultType]:
    for order in orders:
        query = apply_order(query=query, table=table, order=order)
    return query


def get_string_field_filter_conditions(table: DatabaseTable, fieldFilter: StringFieldFilter) -> list[ColumnElement[bool]]:
    field = table.c[fieldFilter.fieldName]
    conditions: list[ColumnElement[bool]] = []
    if fieldFilter.eq is not None:
        conditions.append(field == fieldFilter.eq)
    if fieldFilter.ne is not None:
        conditions.append(field != fieldFilter.ne)
    if fieldFilter.containedIn is not None:
        conditions.append(field.in_(fieldFilter.containedIn))
    if fieldFilter.notContainedIn is not None:
        conditions.append(field.not_in(fieldFilter.notContainedIn))
    return conditions


def get_uuid_field_filter_conditions(table: DatabaseTable, fieldFilter: UUIDFieldFilter) -> list[ColumnElement[bool]]:
    field = table.c[fieldFilter.fieldName]
    conditions: list[ColumnElement[bool]] = []
    if fieldFilter.eq is not None:
        conditions.append(field == uuid_from_value(value=fieldFilter.eq))
    if fieldFilter.ne is not None:
        conditions.append(field != uuid_from_value(value=fieldFilter.ne))
    if fieldFilter.containedIn is not None:
        conditions.append(field.in_([uuid_from_value(value=value) for value in fieldFilter.containedIn]))
    if fieldFilter.notContainedIn is not None:
        conditions.append(field.not_in([uuid_from_value(value=value) for value in fieldFilter.notContainedIn]))
    return conditions


def get_date_field_filter_conditions(table: DatabaseTable, fieldFilter: DateFieldFilter) -> list[ColumnElement[bool]]:
    field = table.c[fieldFilter.fieldName]
    conditions: list[ColumnElement[bool]] = []
    if fieldFilter.eq is not None:
        conditions.append(field == datetime_to_column_value(column=field, dt=fieldFilter.eq))
    if fieldFilter.ne is not None:
        conditions.append(field != datetime_to_column_value(column=field, dt=fieldFilter.ne))
    if fieldFilter.lte is not None:
        conditions.append(field <= datetime_to_column_value(column=field, dt=fieldFilter.lte))
    if fieldFilter.lt is not None:
        conditions.append(field < datetime_to_column_value(column=field, dt=fieldFilter.lt))
    if fieldFilter.gte is not None:
        conditions.append(field >= datetime_to_column_value(column=field, dt=fieldFilter.gte))
    if fieldFilter.gt is not None:
        conditions.append(field > datetime_to_column_value(column=field, dt=fieldFilter.gt))
    if fieldFilter.containedIn is not None:
        conditions.append(field.in_([datetime_to_column_value(column=field, dt=value) for value in fieldFilter.containedIn]))
    if fieldFilter.notContainedIn is not None:
        conditions.append(field.not_in([datetime_to_column_value(column=field, dt=value) for value in fieldFilter.notContainedIn]))
    return conditions


def get_integer_field_filter_conditions(table: DatabaseTable, fieldFilter: IntegerFieldFilter) -> list[ColumnElement[bool]]:
    # NOTE(krishan711): `field == value` / `field.in_(values)` let SQLAlchemy's `Numeric.coerce_compared_value`
    # re-infer a bind param type from the compared Python `int` (typically `BigInteger`, i.e. int64) instead of
    # keeping `field.type` (e.g. `Numeric(78, 0)` for uint256 columns). Binding explicitly with `type_=field.type`
    # avoids an asyncpg `OverflowError` for any value outside the int64 range.
    field = table.c[fieldFilter.fieldName]
    conditions: list[ColumnElement[bool]] = []
    if fieldFilter.eq is not None:
        conditions.append(field == sqlalchemy.bindparam(None, fieldFilter.eq, type_=field.type))
    if fieldFilter.ne is not None:
        conditions.append(field != sqlalchemy.bindparam(None, fieldFilter.ne, type_=field.type))
    if fieldFilter.lte is not None:
        conditions.append(field <= sqlalchemy.bindparam(None, fieldFilter.lte, type_=field.type))
    if fieldFilter.lt is not None:
        conditions.append(field < sqlalchemy.bindparam(None, fieldFilter.lt, type_=field.type))
    if fieldFilter.gte is not None:
        conditions.append(field >= sqlalchemy.bindparam(None, fieldFilter.gte, type_=field.type))
    if fieldFilter.gt is not None:
        conditions.append(field > sqlalchemy.bindparam(None, fieldFilter.gt, type_=field.type))
    if fieldFilter.containedIn is not None:
        conditions.append(field.in_(sqlalchemy.bindparam(None, fieldFilter.containedIn, type_=field.type, expanding=True)))
    if fieldFilter.notContainedIn is not None:
        conditions.append(field.not_in(sqlalchemy.bindparam(None, fieldFilter.notContainedIn, type_=field.type, expanding=True)))
    return conditions


def get_float_field_filter_conditions(table: DatabaseTable, fieldFilter: FloatFieldFilter) -> list[ColumnElement[bool]]:
    field = table.c[fieldFilter.fieldName]
    conditions: list[ColumnElement[bool]] = []
    if fieldFilter.eq is not None:
        conditions.append(field == fieldFilter.eq)
    if fieldFilter.ne is not None:
        conditions.append(field != fieldFilter.ne)
    if fieldFilter.lte is not None:
        conditions.append(field <= fieldFilter.lte)
    if fieldFilter.lt is not None:
        conditions.append(field < fieldFilter.lt)
    if fieldFilter.gte is not None:
        conditions.append(field >= fieldFilter.gte)
    if fieldFilter.gt is not None:
        conditions.append(field > fieldFilter.gt)
    if fieldFilter.containedIn is not None:
        conditions.append(field.in_(fieldFilter.containedIn))
    if fieldFilter.notContainedIn is not None:
        conditions.append(field.not_in(fieldFilter.notContainedIn))
    return conditions


def get_boolean_field_filter_conditions(table: DatabaseTable, fieldFilter: BooleanFieldFilter) -> list[ColumnElement[bool]]:
    field = table.c[fieldFilter.fieldName]
    conditions: list[ColumnElement[bool]] = []
    if fieldFilter.eq is not None:
        conditions.append(field == fieldFilter.eq)
    if fieldFilter.ne is not None:
        conditions.append(field != fieldFilter.ne)
    return conditions


def get_field_filter_conditions(table: DatabaseTable, fieldFilter: FieldFilter) -> list[ColumnElement[bool]]:
    field = table.c[fieldFilter.fieldName]
    conditions: list[ColumnElement[bool]] = []
    if fieldFilter.isNull:
        conditions.append(field.is_(None))
    if fieldFilter.isNotNull:
        conditions.append(field.is_not(None))
    if isinstance(fieldFilter, StringFieldFilter):
        conditions += get_string_field_filter_conditions(table=table, fieldFilter=fieldFilter)
    if isinstance(fieldFilter, UUIDFieldFilter):
        conditions += get_uuid_field_filter_conditions(table=table, fieldFilter=fieldFilter)
    if isinstance(fieldFilter, DateFieldFilter):
        conditions += get_date_field_filter_conditions(table=table, fieldFilter=fieldFilter)
    if isinstance(fieldFilter, IntegerFieldFilter):
        conditions += get_integer_field_filter_conditions(table=table, fieldFilter=fieldFilter)
    if isinstance(fieldFilter, FloatFieldFilter):
        conditions += get_float_field_filter_conditions(table=table, fieldFilter=fieldFilter)
    if isinstance(fieldFilter, BooleanFieldFilter):
        conditions += get_boolean_field_filter_conditions(table=table, fieldFilter=fieldFilter)
    return conditions


def get_field_filters_conditions(table: DatabaseTable, fieldFilters: Sequence[FieldFilter]) -> list[ColumnElement[bool]]:
    return [condition for fieldFilter in fieldFilters for condition in get_field_filter_conditions(table=table, fieldFilter=fieldFilter)]


def apply_field_filters(query: Select[*ResultType], table: DatabaseTable, fieldFilters: Sequence[FieldFilter]) -> Select[*ResultType]:
    return query.where(*get_field_filters_conditions(table=table, fieldFilters=fieldFilters))


class Retriever:
    def __init__(self, database: Database) -> None:
        self.database = database

    def _apply_order(self, query: Select[*ResultType], table: DatabaseTable, order: Order) -> Select[*ResultType]:
        return apply_order(query=query, table=table, order=order)

    def _apply_orders(self, query: Select[*ResultType], table: DatabaseTable, orders: Sequence[Order]) -> Select[*ResultType]:
        return apply_orders(query=query, table=table, orders=orders)

    def _apply_string_field_filter(self, query: Select[*ResultType], table: DatabaseTable, fieldFilter: StringFieldFilter) -> Select[*ResultType]:
        return query.where(*get_string_field_filter_conditions(table=table, fieldFilter=fieldFilter))

    def _apply_uuid_field_filter(self, query: Select[*ResultType], table: DatabaseTable, fieldFilter: UUIDFieldFilter) -> Select[*ResultType]:
        return query.where(*get_uuid_field_filter_conditions(table=table, fieldFilter=fieldFilter))

    def _apply_date_field_filter(self, query: Select[*ResultType], table: DatabaseTable, fieldFilter: DateFieldFilter) -> Select[*ResultType]:
        return query.where(*get_date_field_filter_conditions(table=table, fieldFilter=fieldFilter))

    def _apply_integer_field_filter(self, query: Select[*ResultType], table: DatabaseTable, fieldFilter: IntegerFieldFilter) -> Select[*ResultType]:
        return query.where(*get_integer_field_filter_conditions(table=table, fieldFilter=fieldFilter))

    def _apply_float_field_filter(self, query: Select[*ResultType], table: DatabaseTable, fieldFilter: FloatFieldFilter) -> Select[*ResultType]:
        return query.where(*get_float_field_filter_conditions(table=table, fieldFilter=fieldFilter))

    def _apply_boolean_field_filter(self, query: Select[*ResultType], table: DatabaseTable, fieldFilter: BooleanFieldFilter) -> Select[*ResultType]:
        return query.where(*get_boolean_field_filter_conditions(table=table, fieldFilter=fieldFilter))

    def _apply_field_filter(self, query: Select[*ResultType], table: DatabaseTable, fieldFilter: FieldFilter) -> Select[*ResultType]:
        return query.where(*get_field_filter_conditions(table=table, fieldFilter=fieldFilter))

    def _apply_field_filters(self, query: Select[*ResultType], table: DatabaseTable, fieldFilters: Sequence[FieldFilter]) -> Select[*ResultType]:
        return apply_field_filters(query=query, table=table, fieldFilters=fieldFilters)
