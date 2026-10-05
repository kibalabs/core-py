import typing
import uuid
from collections.abc import Sequence

import sqlalchemy
from pydantic import BaseModel
from sqlalchemy.dialects import postgresql as sqlalchemy_psql
from sqlalchemy.dialects import sqlite as sqlalchemy_sqlite
from sqlalchemy.engine import Result
from sqlalchemy.engine import RowMapping
from sqlalchemy.sql import Select

from core.exceptions import KibaException
from core.exceptions import NotFoundException
from core.store.database import Database
from core.store.database import DatabaseConnection
from core.store.retriever import FieldFilter
from core.store.retriever import Order
from core.store.retriever import apply_field_filters
from core.store.retriever import apply_orders
from core.store.retriever import datetime_to_column_value
from core.store.retriever import get_field_filters_conditions
from core.store.retriever import uuid_from_value
from core.util import date_util

EntityType = typing.TypeVar('EntityType', bound=BaseModel)


class EntityRepository(typing.Generic[EntityType]):  # noqa: UP046
    """Reads and writes rows of a table as pydantic models.

    UUID columns are exposed as strings, datetimes as aware utc datetimes and pydantic values in JSON columns are dumped
    on write. `createdDate` and `updatedDate` columns are stamped automatically when the table has them. Override
    `_convert_value_from_db` and `_convert_value_to_db` to add conversions for other columns, and `list_select_columns`
    with `_get_field_values` to read extra (e.g. computed) columns into the model.
    """

    def __init__(
        self,
        table: sqlalchemy.Table,
        modelClass: type[EntityType],
    ) -> None:
        self.table = table
        self.modelClass = modelClass
        try:
            self.idColumn = next(column for column in table.columns if column.primary_key)
        except StopIteration:
            raise KibaException(f'Failed to find id column for table: {table.name}')

    def _convert_value_from_db(self, column: sqlalchemy.Column[typing.Any], value: typing.Any | None) -> typing.Any | None:  # type: ignore[explicit-any]
        if value is None:
            return None
        if isinstance(column.type, sqlalchemy.Uuid):
            return str(value)
        if isinstance(column.type, sqlalchemy.DateTime):
            return date_util.datetime_to_utc(dt=value)
        return value

    def _convert_value_to_db(self, column: sqlalchemy.Column[typing.Any], value: typing.Any | None) -> typing.Any | None:  # type: ignore[explicit-any]
        if value is None:
            return None
        if isinstance(column.type, sqlalchemy.Uuid):
            return uuid_from_value(value=value)
        if isinstance(column.type, sqlalchemy.DateTime):
            return datetime_to_column_value(column=column, dt=value)
        if isinstance(column.type, sqlalchemy.JSON) and isinstance(value, BaseModel):
            return value.model_dump()
        return value

    def list_select_columns(self) -> list[sqlalchemy.ColumnElement[typing.Any]]:  # type: ignore[explicit-any]
        return list(self.table.columns)

    def build_select(self) -> Select[*tuple[typing.Any, ...]]:  # type: ignore[explicit-any]
        return sqlalchemy.select(*self.list_select_columns())

    def _get_field_values(self, row: RowMapping) -> dict[str, typing.Any]:  # type: ignore[explicit-any]
        return {column.key: self._convert_value_from_db(column=column, value=row[column]) for column in self.table.columns}

    def from_row(self, row: RowMapping) -> EntityType:
        return self.modelClass.model_validate(self._get_field_values(row=row))

    def force_from_result(self, result: Result[typing.Any]) -> EntityType:  # type: ignore[explicit-any]
        row = result.mappings().first()
        if row is None:
            raise NotFoundException
        return self.from_row(row=row)

    def _get_column_names(self) -> str:
        return ', '.join(column.key for column in self.table.columns)

    def _create_values(self, kwargs: dict[str, typing.Any], shouldAddCreatedDate: bool = False, shouldAddUpdatedDate: bool = False) -> dict[sqlalchemy.Column[typing.Any], typing.Any]:  # type: ignore[explicit-any]
        currentDate = date_util.datetime_from_now()
        values: dict[sqlalchemy.Column[typing.Any], typing.Any] = {}  # type: ignore[explicit-any]
        # NOTE(krishan711): immutable tables (e.g. event logs) may have no `updatedDate` column, so this only stamps the
        # columns the table actually defines.
        createdDateColumn = self.table.c.get('createdDate')
        if shouldAddCreatedDate and createdDateColumn is not None:
            values[createdDateColumn] = self._convert_value_to_db(column=createdDateColumn, value=currentDate)
        updatedDateColumn = self.table.c.get('updatedDate')
        if shouldAddUpdatedDate and updatedDateColumn is not None:
            values[updatedDateColumn] = self._convert_value_to_db(column=updatedDateColumn, value=currentDate)
        for key, value in kwargs.items():
            column = self.table.c.get(key)
            if column is None:
                raise KibaException(f'Unknown column: {key}. Valid columns are: {self._get_column_names()}')
            values[column] = self._convert_value_to_db(column=column, value=value)
        return values

    def _add_generated_id(self, values: dict[sqlalchemy.Column[typing.Any], typing.Any]) -> None:  # type: ignore[explicit-any]
        if isinstance(self.idColumn.type, sqlalchemy.Uuid) and values.get(self.idColumn) is None:
            values[self.idColumn] = uuid.uuid4()

    def _create_upsert_insert(self, database: Database) -> sqlalchemy_psql.Insert | sqlalchemy_sqlite.Insert:
        dialectName = database.get_dialect_name()
        if dialectName == 'postgresql':
            return sqlalchemy_psql.insert(self.table)
        if dialectName == 'sqlite':
            return sqlalchemy_sqlite.insert(self.table)
        raise KibaException(f'EntityRepository upserts do not support dialect: {dialectName}')

    # Writing

    async def create(self, database: Database, connection: DatabaseConnection | None = None, **kwargs) -> EntityType:  # type: ignore[no-untyped-def]  # noqa: ANN003
        createValues = self._create_values(kwargs=kwargs, shouldAddCreatedDate=True, shouldAddUpdatedDate=True)
        self._add_generated_id(values=createValues)
        result = await database.execute(query=self.table.insert().values(createValues).returning(*self.list_select_columns()), connection=connection)
        return self.force_from_result(result=result)

    async def update(self, database: Database, connection: DatabaseConnection | None = None, **kwargs) -> EntityType:  # type: ignore[no-untyped-def]  # noqa: ANN003
        updateValues = self._create_values(kwargs=kwargs, shouldAddUpdatedDate=True)
        idValue: typing.Any | None = updateValues.pop(self.idColumn, None)  # type: ignore[explicit-any]
        if idValue is None:
            raise KibaException(f'Failed to find id value for update to {self.table.name}')
        result = await database.execute(query=self.table.update().where(self.idColumn == idValue).values(updateValues).returning(*self.list_select_columns()), connection=connection)
        return self.force_from_result(result=result)

    async def upsert(self, database: Database, constraintColumnNames: list[str], connection: DatabaseConnection | None = None, **kwargs) -> EntityType:  # type: ignore[no-untyped-def]  # noqa: ANN003
        updateValues = self._create_values(kwargs=kwargs, shouldAddUpdatedDate=True, shouldAddCreatedDate=False)
        insertValues = self._create_values(kwargs=kwargs, shouldAddUpdatedDate=True, shouldAddCreatedDate=True)
        self._add_generated_id(values=insertValues)
        insertStatement = self._create_upsert_insert(database=database).values(insertValues)
        constraintColumns = [self.table.c[columnName] for columnName in constraintColumnNames]
        doUpdateStatement = insertStatement.on_conflict_do_update(
            index_elements=constraintColumns,
            set_=updateValues,
        )
        result = await database.execute(query=doUpdateStatement.returning(*self.list_select_columns()), connection=connection)
        return self.force_from_result(result=result)

    async def upsert_many(self, database: Database, constraintColumnNames: list[str], rowDicts: list[dict[str, typing.Any]], connection: DatabaseConnection | None = None) -> list[EntityType]:  # type: ignore[explicit-any]
        if not rowDicts:
            return []
        insertValuesList = [self._create_values(kwargs=row, shouldAddUpdatedDate=True, shouldAddCreatedDate=True) for row in rowDicts]
        for insertValues in insertValuesList:
            self._add_generated_id(values=insertValues)
        constraintColumns = [self.table.c[columnName] for columnName in constraintColumnNames]
        insertStatement = self._create_upsert_insert(database=database).values(insertValuesList)
        excludedColumnKeys = {self.idColumn.key, 'createdDate'}
        updateColumnKeys = {column.key for insertValues in insertValuesList for column in insertValues} - excludedColumnKeys
        doUpdateStatement = insertStatement.on_conflict_do_update(
            index_elements=constraintColumns,
            set_={key: insertStatement.excluded[key] for key in updateColumnKeys},
        )
        result = await database.execute(query=doUpdateStatement.returning(*self.list_select_columns()), connection=connection)
        return [self.from_row(row=row) for row in result.mappings().all()]

    async def delete(self, database: Database, fieldFilters: Sequence[FieldFilter], connection: DatabaseConnection | None = None) -> None:
        query = self.table.delete().where(*get_field_filters_conditions(table=self.table, fieldFilters=fieldFilters))
        await database.execute(query=query, connection=connection)

    # Reading

    async def list_many(self, database: Database, fieldFilters: Sequence[FieldFilter] | None = None, orders: Sequence[Order] | None = None, limit: int | None = None, offset: int | None = None, connection: DatabaseConnection | None = None) -> list[EntityType]:
        query = self.build_select()
        if fieldFilters is not None:
            query = apply_field_filters(query=query, table=self.table, fieldFilters=fieldFilters)
        if orders is not None:
            query = apply_orders(query=query, table=self.table, orders=orders)
        if limit is not None:
            query = query.limit(limit)
        if offset is not None:
            query = query.offset(offset)
        result = await database.execute(query=query, connection=connection)
        return [self.from_row(row=row) for row in result.mappings()]

    async def get_first(self, database: Database, fieldFilters: Sequence[FieldFilter] | None = None, orders: Sequence[Order] | None = None, connection: DatabaseConnection | None = None) -> EntityType | None:
        entities = await self.list_many(database=database, fieldFilters=fieldFilters, orders=orders, limit=1, connection=connection)
        return next(iter(entities), None)

    async def get(self, database: Database, idValue: typing.Any, connection: DatabaseConnection | None = None) -> EntityType:  # type: ignore[explicit-any]
        query = self.build_select().where(self.idColumn == self._convert_value_to_db(column=self.idColumn, value=idValue))
        result = await database.execute(query=query, connection=connection)
        return self.force_from_result(result=result)

    async def get_one(self, database: Database, fieldFilters: Sequence[FieldFilter], connection: DatabaseConnection | None = None) -> EntityType:
        query = apply_field_filters(query=self.build_select(), table=self.table, fieldFilters=fieldFilters)
        result = await database.execute(query=query, connection=connection)
        # TODO(krishan711): raise an exception if there is more than one result
        return self.force_from_result(result=result)

    async def get_one_or_none(self, database: Database, fieldFilters: Sequence[FieldFilter], connection: DatabaseConnection | None = None) -> EntityType | None:
        try:
            return await self.get_one(database=database, fieldFilters=fieldFilters, connection=connection)
        except NotFoundException:
            return None
