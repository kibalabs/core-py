import logging
from typing import Dict
from typing import Optional

import asyncpg
from databases import Database
from sqlalchemy.sql import ClauseElement

from core.exceptions import DuplicateValueException
from core.exceptions import InternalServerErrorException


class Saver:

    def __init__(self, database: Database):
        self.database = database

    async def _execute(self, query: ClauseElement, values: Optional[Dict]):
        try:
            return await self.database.execute(query=query, values=values)
        except asyncpg.exceptions.UniqueViolationError as exception:
            raise DuplicateValueException(message=str(exception)) from exception
        except Exception as exception:
            logging.error(exception)
            raise InternalServerErrorException(message='Error running save operation') from exception
