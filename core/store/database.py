import contextlib
import contextvars
import typing
from collections.abc import AsyncIterator
from typing import TypeVar

import sqlalchemy
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql.selectable import TypedReturnsRows

from core import logging
from core.exceptions import InternalServerErrorException

DatabaseConnection = AsyncConnection
ResultType = TypeVar('ResultType', bound=tuple)  # type: ignore[type-arg]


class Database:
    @staticmethod
    def create_connection_string(engine: str, username: str, password: str, host: str, port: str, name: str) -> str:
        return f'{engine}://{username}:{password}@{host}:{port}/{name}'

    @staticmethod
    def create_psql_connection_string(username: str, password: str, host: str, port: str, name: str) -> str:
        return Database.create_connection_string(engine='postgresql+asyncpg', username=username, password=password, host=host, port=port, name=name)

    @staticmethod
    def create_sqlite_connection_string(filename: str) -> str:
        return f'sqlite+aiosqlite:///{filename}'

    def __init__(self, connectionString: str) -> None:
        self.connectionString = connectionString
        self._engine: AsyncEngine | None = None
        self._connectionContext = contextvars.ContextVar[DatabaseConnection | None]('_connectionContext')

    async def connect(self, poolSize: int = 100) -> None:
        if not self._engine:
            self._engine = create_async_engine(
                self.connectionString,
                # echo_pool=True,
                # hide_parameters=False,
                pool_size=poolSize,
                pool_recycle=3600,
                pool_pre_ping=True,
            )

    async def disconnect(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None

    @contextlib.asynccontextmanager
    async def create_transaction(self) -> AsyncIterator[DatabaseConnection]:
        if not self._engine:
            raise InternalServerErrorException(message='Engine has not been established. Please called collect() first.')
        async with self._engine.begin() as connection:
            yield connection

    def _get_context_connection(self) -> DatabaseConnection | None:
        try:
            connection = self._connectionContext.get()
            if connection and not connection.closed:
                return connection
        except LookupError:
            pass
        return None

    # NOTE(krishan711): this is a little confusing. We creaete a connection for each erquest
    # but if anything inside that request wants to do parallel queries, they should create
    # their own transaction using `self.database.create_transaction()`, because asyncpg (and psql)
    # do not support parallel queries on the same connection. This shows up badly if there is an
    # uncaught exception raised whilst parallel queries are running.
    # We have the forced reconnect at the bottom just to catch for this wierd case.
    @contextlib.asynccontextmanager
    async def create_context_connection(self) -> AsyncIterator[DatabaseConnection]:
        if not self._engine:
            raise InternalServerErrorException(message='Engine has not been established. Please called collect() first.')
        if self._get_context_connection() is not None:
            raise InternalServerErrorException(message='Connection has already been established in this context.')
        connection = None
        try:
            async with self._engine.begin() as connection:
                self._connectionContext.set(connection)
                try:
                    yield connection
                finally:
                    self._connectionContext.set(None)
        except sqlalchemy.exc.InterfaceError as exception:
            if 'cannot perform operation: another operation is in progress' not in str(exception):
                raise
            logging.error(f'Database connection error (likely concurrent operations): {exception}. Forcing reconnect. You MUST ensure that you are not running parallel queries on the same connection.')
            await self.disconnect()
            await self.connect()

    async def execute(self, query: TypedReturnsRows[ResultType], connection: DatabaseConnection | None = None) -> Result[ResultType]:
        if not self._engine:
            raise InternalServerErrorException(message='Connection has not been established. Please called collect() first.')
        if not connection:
            connection = self._get_context_connection()
        if not connection:
            raise InternalServerErrorException(message='No connection found. Please provide a connection or call create_context_connection() for the context.')
        return typing.cast(Result[ResultType], await connection.execute(statement=query))
