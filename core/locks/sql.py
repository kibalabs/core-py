import asyncio
import time
import uuid

import sqlalchemy
from sqlalchemy.dialects import postgresql as sqlalchemy_psql
from sqlalchemy.dialects import sqlite as sqlalchemy_sqlite

from core.exceptions import InternalServerErrorException
from core.exceptions import LockedException
from core.locks.lock import Lock
from core.locks.model import LockLease
from core.store.database import Database
from core.store.database import DatabaseTable
from core.util import date_util
from core.util import process_util

# NOTE(krishan711): this table is owned here (not in the consuming app's schema.py) so it can ship with
# core-py. To include it in an app's own alembic-tracked metadata (so autogenerate creates the table),
# call `LocksTable.to_metadata(appMetadata)` from the app's schema module.
LocksMetadata = sqlalchemy.MetaData()

LocksTable = sqlalchemy.Table(
    'tbl_locks',
    LocksMetadata,
    sqlalchemy.Column(key='name', name='name', type_=sqlalchemy.Text, primary_key=True, nullable=False),
    sqlalchemy.Column(key='lockToken', name='lock_token', type_=sqlalchemy.Text, nullable=False),
    sqlalchemy.Column(key='acquiredDate', name='acquired_date', type_=sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column(key='expiryDate', name='expiry_date', type_=sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column(key='owner', name='owner', type_=sqlalchemy.Text, nullable=False),
)


class SqlLock(Lock):
    def __init__(self, database: Database, table: DatabaseTable = LocksTable, pollIntervalSeconds: float = 1.0, owner: str | None = None) -> None:
        self.database = database
        self.table = table
        self.pollIntervalSeconds = pollIntervalSeconds
        self.owner = owner or process_util.get_process_name()

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def acquire(self, name: str, ttlSeconds: int = 60, maxWaitSeconds: float = 0) -> LockLease:
        deadline = time.monotonic() + maxWaitSeconds
        while True:
            lease = await self._try_acquire(name=name, ttlSeconds=ttlSeconds)
            if lease is not None:
                return lease
            if time.monotonic() >= deadline:
                owner = await self.get_owner(name=name)
                raise LockedException(message=f'LOCK_HELD: {name} by {owner}')
            await asyncio.sleep(min(self.pollIntervalSeconds, max(deadline - time.monotonic(), 0)))

    async def get_owner(self, name: str) -> str | None:
        async with self.database.create_transaction() as connection:
            query = sqlalchemy.select(self.table.c.owner).where(self.table.c.name == name).where(self.table.c.expiryDate > self.database.now())
            result = await self.database.execute(query=query, connection=connection)
            return result.scalar_one_or_none()

    def _create_insert(self, dialectName: str) -> sqlalchemy_psql.Insert | sqlalchemy_sqlite.Insert:
        if dialectName == 'postgresql':
            return sqlalchemy_psql.insert(self.table)
        if dialectName == 'sqlite':
            return sqlalchemy_sqlite.insert(self.table)
        raise InternalServerErrorException(message=f'SqlLock does not support dialect: {dialectName}')

    async def _try_acquire(self, name: str, ttlSeconds: int) -> LockLease | None:
        lease = LockLease(name=name, token=str(uuid.uuid4()), expiryDate=date_util.datetime_from_now(seconds=ttlSeconds), ttlSeconds=ttlSeconds)
        values = {self.table.c.lockToken: lease.token, self.table.c.acquiredDate: self.database.now(), self.table.c.expiryDate: self.database.now(seconds=ttlSeconds), self.table.c.owner: self.owner}
        async with self.database.create_transaction() as connection:
            upsertQuery = (
                self._create_insert(dialectName=connection.dialect.name)
                .values({self.table.c.name: name, **values})
                .on_conflict_do_update(index_elements=[self.table.c.name], set_=values, where=self.table.c.expiryDate <= self.database.now())
                .returning(self.table.c.name)
            )
            result = await self.database.execute(query=upsertQuery, connection=connection)
            isAcquired = result.first() is not None
        return lease if isAcquired else None

    async def extend(self, lease: LockLease, ttlSeconds: int = 60) -> bool:
        newExpiryDate = date_util.datetime_from_now(seconds=ttlSeconds)
        async with self.database.create_transaction() as connection:
            updateQuery = (
                sqlalchemy.update(self.table)
                .where(self.table.c.name == lease.name)
                .where(self.table.c.lockToken == lease.token)
                .where(self.table.c.expiryDate > self.database.now())
                .values(expiryDate=self.database.now(seconds=ttlSeconds))
                .returning(self.table.c.name)
            )
            result = await self.database.execute(query=updateQuery, connection=connection)
            isExtended = result.first() is not None
        if isExtended:
            lease.expiryDate = newExpiryDate
        return isExtended

    async def release(self, lease: LockLease) -> None:
        async with self.database.create_transaction() as connection:
            deleteQuery = sqlalchemy.delete(self.table).where(self.table.c.name == lease.name).where(self.table.c.lockToken == lease.token)
            await self.database.execute(query=deleteQuery, connection=connection)
