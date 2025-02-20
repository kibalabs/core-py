import contextlib
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy import Table
from sqlalchemy.engine import Result
from sqlalchemy.sql.selectable import TypedReturnsRows

from core.exceptions import InternalServerErrorException
from core.store.database import Database
from core.store.database import DatabaseConnection
from core.store.database import ResultType

if TYPE_CHECKING:
    from sqlalchemy.sql._typing import _ColumnExpressionArgument
    from sqlalchemy.sql._typing import _DMLColumnArgument

    WhereClause = _ColumnExpressionArgument[bool]
else:
    _DMLColumnArgument = Any
    WhereClause = Any


CreateRecordValuesDict = dict[_DMLColumnArgument, Any]  # type: ignore[explicit-any]
UpdateRecordValuesDict = dict[_DMLColumnArgument, Any]  # type: ignore[explicit-any]


class SavingException(InternalServerErrorException):
    pass


class Saver:
    def __init__(self, database: Database) -> None:
        self.database = database

    @contextlib.asynccontextmanager
    async def create_transaction(self) -> AsyncIterator[DatabaseConnection]:
        async with self.database.create_transaction() as connection:
            yield connection

    async def _execute(self, query: TypedReturnsRows[ResultType], connection: DatabaseConnection | None = None) -> Result[ResultType]:
        try:
            if connection:
                return await self.database.execute(query=query, connection=connection)
            async with self.create_transaction() as newConnection:
                return await self.database.execute(query=query, connection=newConnection)
        # NOTE(krishan711): this could probs be more specific e.g. sqlalchemy.dialects.postgresql.asyncpg.IntegrityError
        except Exception as exception:
            raise SavingException(message=f'Error running save operation: {exception!s}') from exception

    async def _insert_record(self, table: Table, values: CreateRecordValuesDict, connection: DatabaseConnection | None = None) -> int:
        query = table.insert().values(values).returning(table.c.id)
        result = await self._execute(query=query, connection=connection)
        rowId = int(result.scalar_one())
        return rowId

    async def _update_records(self, table: Table, where: WhereClause, values: UpdateRecordValuesDict, connection: DatabaseConnection | None = None) -> list[int]:
        query = table.update().where(where).values(values).returning(table.c.id)
        result = await self._execute(query=query, connection=connection)
        rowIds = [int(rowId) for rowId in result.scalars()]
        return rowIds

    async def _delete_records(self, table: Table, where: WhereClause, connection: DatabaseConnection | None = None) -> list[int]:
        query = table.delete().where(where).returning(table.c.id)
        result = await self._execute(query=query, connection=connection)
        rowIds = [int(rowId) for rowId in result.scalars()]
        return rowIds
