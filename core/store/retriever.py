import dataclasses
import datetime
from enum import Enum
from typing import Optional
from typing import Sequence

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
    isNull: Optional[bool] = None
    isNotNull: Optional[bool] = None

@dataclasses.dataclass
class StringFieldFilter(FieldFilter):
    eq: Optional[str] = None
    ne: Optional[str] = None
    containedIn: Optional[Sequence[str]] = None
    notContainedIn: Optional[Sequence[str]] = None

@dataclasses.dataclass
class DateFieldFilter(FieldFilter):
    eq: Optional[datetime.datetime] = None
    ne: Optional[datetime.datetime] = None
    lte: Optional[datetime.datetime] = None
    lt: Optional[datetime.datetime] = None
    gte: Optional[datetime.datetime] = None
    gt: Optional[datetime.datetime] = None
    containedIn: Optional[Sequence[datetime.datetime]] = None
    notContainedIn: Optional[Sequence[datetime.datetime]] = None

@dataclasses.dataclass
class IntegerFieldFilter(FieldFilter):
    eq: Optional[int] = None
    ne: Optional[int] = None
    lte: Optional[int] = None
    lt: Optional[int] = None
    gte: Optional[int] = None
    gt: Optional[int] = None
    containedIn: Optional[Sequence[int]] = None
    notContainedIn: Optional[Sequence[int]] = None

@dataclasses.dataclass
class FloatFieldFilter(FieldFilter):
    eq: Optional[float] = None
    ne: Optional[float] = None
    lte: Optional[float] = None
    lt: Optional[float] = None
    gte: Optional[float] = None
    gt: Optional[float] = None
    containedIn: Optional[Sequence[float]] = None
    notContainedIn: Optional[Sequence[float]] = None

class Retriever:

    def __init__(self, database: Database):
        self.database = database

    def _apply_order(self, query: Select[ResultType], table: Table, order: Order) -> Select[ResultType]:
        if isinstance(order, RandomOrder):
            query = query.order_by(sqlalchemy.func.random())
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
        return query

    def _apply_field_filters(self, query: Select[ResultType], table: Table, fieldFilters: Sequence[FieldFilter]) -> Select[ResultType]:
        for fieldFilter in fieldFilters:
            query = self._apply_field_filter(query=query, table=table, fieldFilter=fieldFilter)
        return query
