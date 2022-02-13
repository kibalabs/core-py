import contextlib
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
        self._connection = None

    async def connect(self):
        if not self._engine:
            self._engine = create_async_engine(self.connectionString, future=True)
        if not self._connection:
            self._connection = self._engine.connect()
            await self._connection.start()

    async def disconnect(self):
        if self._connection:
            await self._connection.close()
            self._connection = None
        if self._engine:
            await self._engine.dispose()
            self._engine = None

    @contextlib.asynccontextmanager
    async def create_transaction(self) -> ContextManager[DatabaseConnection]:
        async with self._engine.begin() as connection:
            yield connection

    async def execute(self, query: ClauseElement, connection: Optional[DatabaseConnection] = None):
        connection = connection or self._connection
        result = await connection.execute(statement=query)
        return result
