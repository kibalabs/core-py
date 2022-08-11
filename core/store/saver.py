import contextlib
from typing import Optional

from sqlalchemy.sql import ClauseElement

from core.exceptions import InternalServerErrorException
from core.store.database import Database
from core.store.database import DatabaseConnection


class SavingException(InternalServerErrorException):
    pass


class Saver:

    def __init__(self, database: Database):
        self.database = database

    @contextlib.asynccontextmanager
    async def create_transaction(self):
        async with self.database.create_transaction() as connection:
            yield connection

    async def _execute(self, query: ClauseElement, connection: Optional[DatabaseConnection] = None):
        try:
            if connection:
                return await self.database.execute(query=query, connection=connection)
            async with self.create_transaction() as connection:
                return await self.database.execute(query=query, connection=connection)
        # NOTE(krishan711): this could probs be more specific e.g. sqlalchemy.dialects.postgresql.asyncpg.IntegrityError
        except Exception as exception:
            raise SavingException(message=f'Error running save operation: {str(exception)}') from exception
