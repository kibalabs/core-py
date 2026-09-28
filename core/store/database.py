import contextlib
import contextvars
import typing
import weakref
from collections.abc import AsyncIterator
from typing import TypeVar

import sqlalchemy
import sqlalchemy.exc
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql.dml import UpdateBase
from sqlalchemy.sql.selectable import TypedReturnsRows

from core import logging
from core.exceptions import InternalServerErrorException
from core.util import json_util

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
        self._connectionsWithWrites = weakref.WeakSet[DatabaseConnection]()

    async def connect(self, poolSize: int = 100) -> None:
        if not self._engine:
            self._engine = create_async_engine(
                self.connectionString,
                # echo_pool=True,
                # hide_parameters=False,
                json_serializer=json_util.dumps,
                json_deserializer=json_util.loads,
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

    # NOTE(krishan711): unlike create_context_connection this may be used inside an existing context connection.
    # Everything in the block runs on a new transaction that commits when the block exits, independent of the
    # outer transaction, which becomes the context connection again afterwards. It cannot see the outer
    # transaction's uncommitted writes and will block forever on rows the outer transaction has written, so
    # callers must commit their writes before entering. Violations are logged (with the caller's stack) for now.
    @contextlib.asynccontextmanager
    async def create_isolated_context_connection(self) -> AsyncIterator[DatabaseConnection]:
        if not self._engine:
            raise InternalServerErrorException(message='Engine has not been established. Please called collect() first.')
        outerConnection = self._get_context_connection()
        if outerConnection is not None and outerConnection in self._connectionsWithWrites:
            logging.error('ISOLATED_CONNECTION_AFTER_UNCOMMITTED_WRITES: an isolated context connection was opened while the outer context connection has uncommitted writes', stack_info=True)
        async with self._engine.begin() as connection:
            token = self._connectionContext.set(connection)
            try:
                yield connection
            finally:
                self._connectionContext.reset(token)

    @typing.overload
    async def execute(self, query: TypedReturnsRows[ResultType], connection: DatabaseConnection | None = None) -> Result[ResultType]: ...
    @typing.overload
    async def execute(self, query: sqlalchemy.sql.Executable, connection: DatabaseConnection | None = None) -> Result[typing.Any]: ...  # type: ignore[explicit-any]
    async def execute(self, query: sqlalchemy.sql.Executable, connection: DatabaseConnection | None = None) -> Result[typing.Any]:  # type: ignore[explicit-any]
        if not self._engine:
            raise InternalServerErrorException(message='Connection has not been established. Please called collect() first.')
        if not connection:
            connection = self._get_context_connection()
        if not connection:
            raise InternalServerErrorException(message='No connection found. Please provide a connection or call create_context_connection() for the context.')
        if isinstance(query, UpdateBase):
            self._connectionsWithWrites.add(connection)
        return typing.cast(Result[typing.Any], await connection.execute(statement=query))  # type: ignore[explicit-any]
