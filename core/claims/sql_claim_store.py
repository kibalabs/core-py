import datetime

import sqlalchemy
from sqlalchemy.dialects import postgresql as sqlalchemy_psql
from sqlalchemy.dialects import sqlite as sqlalchemy_sqlite

from core.claims.claim_store import ClaimStore
from core.exceptions import InternalServerErrorException
from core.store.database import Database
from core.store.database import DatabaseTable

# NOTE(krishan711): like LocksTable, this table ships with core-py. To include it in an app's alembic-tracked metadata
# (so autogenerate creates it), call `ClaimsTable.to_metadata(appMetadata)` from the app's schema module.
ClaimsMetadata = sqlalchemy.MetaData()

ClaimsTable = sqlalchemy.Table(
    'tbl_claims',
    ClaimsMetadata,
    sqlalchemy.Column(key='key', name='key', type_=sqlalchemy.Text, primary_key=True, nullable=False),
    sqlalchemy.Column(key='expiryDate', name='expiry_date', type_=sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Index('tbl_claims_idx_expiry_date', 'expiryDate'),
)


class SqlClaimStore(ClaimStore):
    def __init__(self, database: Database, table: DatabaseTable = ClaimsTable) -> None:
        self.database = database
        self.table = table

    async def claim(self, key: str, lifetime: datetime.timedelta) -> bool:
        async with self.database.create_transaction() as connection:
            await self.database.execute(query=sqlalchemy.delete(self.table).where(self.table.c.expiryDate <= self.database.now()), connection=connection)
            insertQuery = (
                self._create_insert(dialectName=connection.dialect.name)
                .values({self.table.c.key: key, self.table.c.expiryDate: self.database.now(seconds=lifetime.total_seconds())})
                .on_conflict_do_nothing(index_elements=[self.table.c.key])
                .returning(self.table.c.key)
            )
            result = await self.database.execute(query=insertQuery, connection=connection)
            return result.first() is not None

    async def is_claimed(self, key: str) -> bool:
        async with self.database.create_transaction() as connection:
            query = sqlalchemy.select(self.table.c.key).where(self.table.c.key == key).where(self.table.c.expiryDate > self.database.now())
            result = await self.database.execute(query=query, connection=connection)
            return result.first() is not None

    def _create_insert(self, dialectName: str) -> sqlalchemy_psql.Insert | sqlalchemy_sqlite.Insert:
        if dialectName == 'postgresql':
            return sqlalchemy_psql.insert(self.table)
        if dialectName == 'sqlite':
            return sqlalchemy_sqlite.insert(self.table)
        raise InternalServerErrorException(message=f'SqlClaimStore does not support dialect: {dialectName}')
