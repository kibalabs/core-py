import contextlib
import contextvars
import typing
from collections.abc import AsyncIterator
from typing import TypeVar

from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql.selectable import TypedReturnsRows

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

    async def connect(self) -> None:
        if not self._engine:
            self._engine = create_async_engine(self.connectionString, future=True)

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

    @contextlib.asynccontextmanager
    async def create_context_connection(self) -> AsyncIterator[DatabaseConnection]:
        if not self._engine:
            raise InternalServerErrorException(message='Engine has not been established. Please called collect() first.')
        if self._get_context_connection() is not None:
            raise InternalServerErrorException(message='Connection has already been established in this context.')
        async with self._engine.begin() as connection:
            self._connectionContext.set(connection)
            try:
                yield connection
            finally:
                self._connectionContext.set(None)

    async def execute(self, query: TypedReturnsRows[ResultType], connection: DatabaseConnection | None = None) -> Result[ResultType]:
        if not self._engine:
            raise InternalServerErrorException(message='Connection has not been established. Please called collect() first.')
        if not connection:
            connection = self._get_context_connection()
        if not connection:
            raise InternalServerErrorException(message='No connection found. Please provide a connection or call create_context_connection() for the context.')
        return typing.cast(Result[ResultType], await connection.execute(statement=query))
