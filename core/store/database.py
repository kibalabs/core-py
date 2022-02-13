import contextlib
import contextvars
import logging
from typing import ContextManager
from typing import Dict
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
        self._engine = create_async_engine(connectionString, future=True)
        self._connection_context = contextvars.ContextVar("connection_context")
        self._connection = None

    async def connect(self):
        if self._connection:
            return
        self._connection = await self._engine.connect()

    async def disconnect(self):
        if not self._connection:
            return
        await self._connection.close()

    @contextlib.asynccontextmanager
    async def create_transaction(self) -> ContextManager[DatabaseConnection]:
        async with self._engine.begin() as connection:
            yield connection

    async def execute(self, query: ClauseElement, connection: Optional[DatabaseConnection] = None):
        connection = connection or self._connection
        result = await connection.execute(statement=query)
        return result
