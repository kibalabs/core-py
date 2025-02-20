import dataclasses
import datetime
from collections.abc import Sequence
from enum import Enum

import sqlalchemy
from sqlalchemy import Table
from sqlalchemy.sql import Select

from core.store.database import Database
from core.store.database import ResultType


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


class Retriever:
    def __init__(self, database: Database) -> None:
        self.database = database

    def _apply_order(self, query: Select[ResultType], table: Table, order: Order) -> Select[ResultType]:
        if isinstance(order, RandomOrder):
            query = query.order_by(sqlalchemy.sql.functions.random())
        else:
            field = table.c[order.fieldName]
            query = query.order_by(field.asc() if order.direction == Direction.ASCENDING else field.desc())
        return query

    def _apply_orders(self, query: Select[ResultType], table: Table, orders: Sequence[Order]) -> Select[ResultType]:
        for order in orders:
            query = self._apply_order(query=query, table=table, order=order)
        return query

    def _apply_string_field_filter(self, query: Select[ResultType], table: Table, fieldFilter: StringFieldFilter) -> Select[ResultType]:
        field = table.c[fieldFilter.fieldName]
        if fieldFilter.eq is not None:
            query = query.where(field == fieldFilter.eq)
        if fieldFilter.ne is not None:
            query = query.where(field != fieldFilter.ne)
        if fieldFilter.containedIn is not None:
            query = query.where(field.in_(fieldFilter.containedIn))
        if fieldFilter.notContainedIn is not None:
            query = query.where(field.not_in(fieldFilter.notContainedIn))
        return query

    def _apply_date_field_filter(self, query: Select[ResultType], table: Table, fieldFilter: DateFieldFilter) -> Select[ResultType]:
        field = table.c[fieldFilter.fieldName]
        if fieldFilter.eq is not None:
            query = query.where(field == fieldFilter.eq)
        if fieldFilter.ne is not None:
            query = query.where(field != fieldFilter.ne)
        if fieldFilter.lte is not None:
            query = query.where(field <= fieldFilter.lte)
        if fieldFilter.lt is not None:
            query = query.where(field < fieldFilter.lt)
        if fieldFilter.gte is not None:
            query = query.where(field >= fieldFilter.gte)
        if fieldFilter.gt is not None:
            query = query.where(field > fieldFilter.gt)
        if fieldFilter.containedIn is not None:
            query = query.where(field.in_(fieldFilter.containedIn))
        if fieldFilter.notContainedIn is not None:
            query = query.where(field.not_in(fieldFilter.notContainedIn))
        return query

    def _apply_integer_field_filter(self, query: Select[ResultType], table: Table, fieldFilter: IntegerFieldFilter) -> Select[ResultType]:
        field = table.c[fieldFilter.fieldName]
        if fieldFilter.eq is not None:
            query = query.where(field == fieldFilter.eq)
        if fieldFilter.ne is not None:
            query = query.where(field != fieldFilter.ne)
        if fieldFilter.lte is not None:
            query = query.where(field <= fieldFilter.lte)
        if fieldFilter.lt is not None:
            query = query.where(field < fieldFilter.lt)
        if fieldFilter.gte is not None:
            query = query.where(field >= fieldFilter.gte)
        if fieldFilter.gt is not None:
            query = query.where(field > fieldFilter.gt)
        if fieldFilter.containedIn is not None:
            query = query.where(field.in_(fieldFilter.containedIn))
        if fieldFilter.notContainedIn is not None:
            query = query.where(field.not_in(fieldFilter.notContainedIn))
        return query

    def _apply_float_field_filter(self, query: Select[ResultType], table: Table, fieldFilter: FloatFieldFilter) -> Select[ResultType]:
        field = table.c[fieldFilter.fieldName]
        if fieldFilter.eq is not None:
            query = query.where(field == fieldFilter.eq)
        if fieldFilter.ne is not None:
            query = query.where(field != fieldFilter.ne)
        if fieldFilter.lte is not None:
            query = query.where(field <= fieldFilter.lte)
        if fieldFilter.lt is not None:
            query = query.where(field < fieldFilter.lt)
        if fieldFilter.gte is not None:
            query = query.where(field >= fieldFilter.gte)
        if fieldFilter.gt is not None:
            query = query.where(field > fieldFilter.gt)
        if fieldFilter.containedIn is not None:
            query = query.where(field.in_(fieldFilter.containedIn))
        if fieldFilter.notContainedIn is not None:
            query = query.where(field.not_in(fieldFilter.notContainedIn))
        return query

    def _apply_boolean_field_filter(self, query: Select[ResultType], table: Table, fieldFilter: BooleanFieldFilter) -> Select[ResultType]:
        field = table.c[fieldFilter.fieldName]
        if fieldFilter.eq is not None:
            query = query.where(field == fieldFilter.eq)
        if fieldFilter.ne is not None:
            query = query.where(field != fieldFilter.ne)
        return query

    def _apply_field_filter(self, query: Select[ResultType], table: Table, fieldFilter: FieldFilter) -> Select[ResultType]:
        field = table.c[fieldFilter.fieldName]
        if fieldFilter.isNull:
            query = query.where(field.is_(None))
        if fieldFilter.isNotNull:
            query = query.where(field.is_not(None))
        if isinstance(fieldFilter, StringFieldFilter):
            query = self._apply_string_field_filter(query=query, table=table, fieldFilter=fieldFilter)
        if isinstance(fieldFilter, DateFieldFilter):
            query = self._apply_date_field_filter(query=query, table=table, fieldFilter=fieldFilter)
        if isinstance(fieldFilter, IntegerFieldFilter):
            query = self._apply_integer_field_filter(query=query, table=table, fieldFilter=fieldFilter)
        if isinstance(fieldFilter, FloatFieldFilter):
            query = self._apply_float_field_filter(query=query, table=table, fieldFilter=fieldFilter)
        if isinstance(fieldFilter, BooleanFieldFilter):
            query = self._apply_boolean_field_filter(query=query, table=table, fieldFilter=fieldFilter)
        return query

    def _apply_field_filters(self, query: Select[ResultType], table: Table, fieldFilters: Sequence[FieldFilter]) -> Select[ResultType]:
        for fieldFilter in fieldFilters:
            query = self._apply_field_filter(query=query, table=table, fieldFilter=fieldFilter)
        return query
