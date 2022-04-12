import contextlib
from typing import Optional

import asyncpg
from sqlalchemy.sql import ClauseElement

from core import logging
from core.exceptions import DuplicateValueException
from core.exceptions import InternalServerErrorException
from core.store.database import Database
from core.store.database import DatabaseConnection


class Saver:

    def __init__(self, database: Database):
        self.database = database

    @contextlib.asynccontextmanager
    async def create_transaction(self):
        async with self.database.create_transaction() as connection:
            yield connection

    async def _execute(self, query: ClauseElement, connection: Optional[DatabaseConnection] = None):
        try:
            return await self.database.execute(query=query, connection=connection)
        except asyncpg.exceptions.UniqueViolationError as exception:
            raise DuplicateValueException(message=str(exception)) from exception
        except Exception as exception:
            logging.error(exception)
            raise InternalServerErrorException(message='Error running save operation') from exception
