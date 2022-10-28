import contextlib
import contextvars
import typing
from typing import AsyncIterator
from typing import Optional
from typing import Tuple
from typing import TypeVar

from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql.selectable import TypedReturnsRows

from core.exceptions import InternalServerErrorException

DatabaseConnection = AsyncConnection
ResultType = TypeVar('ResultType', bound=Tuple)  # type: ignore[type-arg]  # pylint: disable=invalid-name


class Database:

    @staticmethod
    def create_connection_string(engine: str, username: str, password: str, host: str, port: str, name: str) -> str:
        return f'{engine}://{username}:{password}@{host}:{port}/{name}'

    @staticmethod
    def create_psql_connection_string(username: str, password: str, host: str, port: str, name: str) -> str:
        return Database.create_connection_string(engine='postgresql+asyncpg', username=username, password=password, host=host, port=port, name=name)

    def __init__(self, connectionString: str):
        self.connectionString = connectionString
        self._engine: Optional[AsyncEngine] = None
        self._connectionContext = contextvars.ContextVar[DatabaseConnection]("_connectionContext")

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

    def _get_connection(self) -> Optional[DatabaseConnection]:
        try:
            connection = self._connectionContext.get()
            if not connection.closed:
                return connection
        except LookupError:
            pass
        return None

    @contextlib.asynccontextmanager
    async def create_context_connection(self) -> AsyncIterator[DatabaseConnection]:
        if not self._engine:
            raise InternalServerErrorException(message='Engine has not been established. Please called collect() first.')
        if self._get_connection() is not None:
            raise InternalServerErrorException(message='Connection has already been established in this context.')
        async with self._engine.begin() as connection:
            self._connectionContext.set(connection)
            yield connection

    async def execute(self, query: TypedReturnsRows[ResultType], connection: Optional[DatabaseConnection] = None) -> Result[ResultType]:
        if not self._engine:
            raise InternalServerErrorException(message='Connection has not been established. Please called collect() first.')
        if connection:
            return typing.cast(Result[ResultType], await connection.execute(statement=query))
        newConnection = self._get_connection()
        if newConnection:
            return typing.cast(Result[ResultType], await newConnection.execute(statement=query))
        async with self._engine.connect() as temporaryConnection:
            return typing.cast(Result[ResultType], await temporaryConnection.execute(statement=query))
