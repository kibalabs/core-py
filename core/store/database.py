import contextlib
import contextvars
from typing import ContextManager
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import ClauseElement


class DatabaseConnection(AsyncConnection):
    pass

class Database:

    @staticmethod
    def create_connection_string(engine: str, username: str, password: str, host: str, port: str, name: str) -> str:
        return f'{engine}://{username}:{password}@{host}:{port}/{name}'

    @staticmethod
    def create_psql_connection_string(username: str, password: str, host: str, port: str, name: str) -> str:
        return Database.create_connection_string(engine='postgresql+asyncpg', username=username, password=password, host=host, port=port, name=name)

    def __init__(self, connectionString: str):
        self.connectionString = connectionString
        self._engine = None
        self._connectionContext = contextvars.ContextVar("_connectionContext")

    async def connect(self):
        if not self._engine:
            self._engine = create_async_engine(self.connectionString, future=True)

    async def disconnect(self):
        if self._engine:
            await self._engine.dispose()
            self._engine = None

    @contextlib.asynccontextmanager
    async def create_transaction(self) -> ContextManager[DatabaseConnection]:
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
    async def create_context_connection(self) -> ContextManager[DatabaseConnection]:
        if self._get_connection() is not None:
            raise Exception
        async with self._engine.begin() as connection:
            self._connectionContext.set(connection)
            yield connection

    async def execute(self, query: ClauseElement, connection: Optional[DatabaseConnection] = None):
        if connection:
            return await connection.execute(statement=query)
        connection = self._get_connection()
        if connection:
            return await connection.execute(statement=query)
        async with self._engine.connect() as connection:
            return await connection.execute(statement=query)
