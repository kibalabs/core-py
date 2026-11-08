import datetime

import sqlalchemy
from sqlalchemy.dialects import postgresql as sqlalchemy_psql
from sqlalchemy.dialects import sqlite as sqlalchemy_sqlite

from core.auth_tokens.auth_token_invalidation_store import AuthTokenInvalidationStore
from core.exceptions import InternalServerErrorException
from core.store.database import Database
from core.store.database import DatabaseTable

# NOTE(krishan711): like LocksTable, this table ships with core-py. To include it in an app's alembic-tracked metadata
# (so autogenerate creates it), call `AuthTokenInvalidationsTable.to_metadata(appMetadata)` from the app's schema module.
AuthTokenInvalidationsMetadata = sqlalchemy.MetaData()

AuthTokenInvalidationsTable = sqlalchemy.Table(
    'tbl_auth_token_invalidations',
    AuthTokenInvalidationsMetadata,
    sqlalchemy.Column(key='id', name='id', type_=sqlalchemy.Integer, autoincrement=True, primary_key=True, nullable=False),
    sqlalchemy.Column(key='createdDate', name='created_date', type_=sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column(key='key', name='key', type_=sqlalchemy.Text, nullable=False),
    sqlalchemy.Column(key='expiryDate', name='expiry_date', type_=sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.UniqueConstraint('key', name='tbl_auth_token_invalidations_ux_key'),
    sqlalchemy.Index('tbl_auth_token_invalidations_idx_expiry_date', 'expiryDate'),
)


class SqlAuthTokenInvalidationStore(AuthTokenInvalidationStore):
    def __init__(self, database: Database, table: DatabaseTable = AuthTokenInvalidationsTable) -> None:
        self.database = database
        self.table = table

    async def invalidate(self, key: str, lifetime: datetime.timedelta) -> bool:
        async with self.database.create_transaction() as connection:
            await self.database.execute(query=sqlalchemy.delete(self.table).where(self.table.c.expiryDate <= self.database.now()), connection=connection)
            insertQuery = (
                self._create_insert(dialectName=connection.dialect.name)
                .values({self.table.c.createdDate: self.database.now(), self.table.c.key: key, self.table.c.expiryDate: self.database.now(seconds=lifetime.total_seconds())})
                .on_conflict_do_nothing(index_elements=[self.table.c.key])
                .returning(self.table.c.key)
            )
            result = await self.database.execute(query=insertQuery, connection=connection)
            return result.first() is not None

    async def is_invalidated(self, key: str) -> bool:
        async with self.database.create_transaction() as connection:
            query = sqlalchemy.select(self.table.c.key).where(self.table.c.key == key).where(self.table.c.expiryDate > self.database.now())
            result = await self.database.execute(query=query, connection=connection)
            return result.first() is not None

    def _create_insert(self, dialectName: str) -> sqlalchemy_psql.Insert | sqlalchemy_sqlite.Insert:
        if dialectName == 'postgresql':
            return sqlalchemy_psql.insert(self.table)
        if dialectName == 'sqlite':
            return sqlalchemy_sqlite.insert(self.table)
        raise InternalServerErrorException(message=f'SqlAuthTokenInvalidationStore does not support dialect: {dialectName}')
