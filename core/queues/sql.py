from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Sequence
from typing import Any

import sqlalchemy
import sqlalchemy.exc
from sqlalchemy import RowMapping
from sqlalchemy.dialects import postgresql as sqlalchemy_psql
from sqlalchemy.dialects import sqlite as sqlalchemy_sqlite

from core.exceptions import InternalServerErrorException
from core.queues.message_queue import MessageQueue
from core.queues.model import Message
from core.store.database import Database
from core.store.database import DatabaseTable
from core.util import process_util

MESSAGE_STATUS_PENDING = 'pending'
MESSAGE_STATUS_RUNNING = 'running'
MESSAGE_STATUS_SUCCEEDED = 'succeeded'
MESSAGE_STATUS_FAILED = 'failed'
MESSAGE_STATUS_DEDUPLICATED = 'deduplicated'

# NOTE(krishan711): must be literal SQL so postgres can match ON CONFLICT against the partial unique index
_PENDING_PREDICATE = sqlalchemy.text(f"status = '{MESSAGE_STATUS_PENDING}'")

# NOTE(krishan711): this table is owned here (not in the consuming app's schema.py) so it can ship with
# core-py. To include it in an app's own alembic-tracked metadata (so autogenerate creates the table),
# call `QueueMessagesTable.to_metadata(appMetadata)` from the app's schema module.
QueueMessagesMetadata = sqlalchemy.MetaData()

QueueMessagesTable = sqlalchemy.Table(
    'tbl_queue_messages',
    QueueMessagesMetadata,
    sqlalchemy.Column(key='id', name='id', type_=sqlalchemy.Integer, autoincrement=True, primary_key=True, nullable=False),
    sqlalchemy.Column(key='createdDate', name='created_date', type_=sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column(key='queueName', name='queue_name', type_=sqlalchemy.Text, nullable=False),
    sqlalchemy.Column(key='command', name='command', type_=sqlalchemy.Text, nullable=False),
    sqlalchemy.Column(key='content', name='content', type_=sqlalchemy.JSON().with_variant(sqlalchemy_psql.JSONB(), 'postgresql'), nullable=False),
    sqlalchemy.Column(key='requestId', name='request_id', type_=sqlalchemy.Text, nullable=True),
    sqlalchemy.Column(key='postCount', name='post_count', type_=sqlalchemy.Integer, nullable=False),
    sqlalchemy.Column(key='postDate', name='post_date', type_=sqlalchemy.DateTime(timezone=True), nullable=True),
    sqlalchemy.Column(key='deduplicationId', name='deduplication_id', type_=sqlalchemy.Text, nullable=True),
    sqlalchemy.Column(key='status', name='status', type_=sqlalchemy.Text, nullable=False),
    sqlalchemy.Column(key='visibleDate', name='visible_date', type_=sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column(key='lockToken', name='lock_token', type_=sqlalchemy.Text, nullable=True),
    sqlalchemy.Column(key='owner', name='owner', type_=sqlalchemy.Text, nullable=True),
    sqlalchemy.Column(key='startedDate', name='started_date', type_=sqlalchemy.DateTime(timezone=True), nullable=True),
    sqlalchemy.Column(key='completedDate', name='completed_date', type_=sqlalchemy.DateTime(timezone=True), nullable=True),
    sqlalchemy.Column(key='lastError', name='last_error', type_=sqlalchemy.Text, nullable=True),
    sqlalchemy.Index('tbl_queue_messages_idx_queue_name_status_visible_date', 'queueName', 'status', 'visibleDate'),
    sqlalchemy.Index('tbl_queue_messages_ux_queue_name_deduplication_id_pending', 'queueName', 'deduplicationId', unique=True, postgresql_where=_PENDING_PREDICATE, sqlite_where=_PENDING_PREDICATE),
)


class SqlMessage(Message):
    id: int
    lockToken: str

    @classmethod
    def from_row(cls, row: RowMapping, table: DatabaseTable) -> SqlMessage:
        return cls(
            id=row[table.c.id],
            command=row[table.c.command],
            content=row[table.c.content],
            requestId=row[table.c.requestId],
            postCount=row[table.c.postCount],
            postDate=row[table.c.postDate],
            deduplicationId=row[table.c.deduplicationId],
            lockToken=row[table.c.lockToken],
        )


class SqlMessageQueue(MessageQueue[SqlMessage]):
    def __init__(
        self,
        database: Database,
        queueName: str,
        table: DatabaseTable = QueueMessagesTable,
        pollIntervalSeconds: float = 1.0,
        maxAttempts: int = 3,
        failureRetryDelaySeconds: int = 60,
        retentionSeconds: int = 7 * 24 * 60 * 60,
        owner: str | None = None,
    ) -> None:
        self.database = database
        self.queueName = queueName
        self.table = table
        self.pollIntervalSeconds = pollIntervalSeconds
        self.maxAttempts = maxAttempts
        self.failureRetryDelaySeconds = failureRetryDelaySeconds
        self.retentionSeconds = retentionSeconds
        self.owner = owner or process_util.get_process_name()

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    def _create_insert(self, dialectName: str) -> sqlalchemy_psql.Insert | sqlalchemy_sqlite.Insert:
        if dialectName == 'postgresql':
            return sqlalchemy_psql.insert(self.table)
        if dialectName == 'sqlite':
            return sqlalchemy_sqlite.insert(self.table)
        raise InternalServerErrorException(message=f'SqlMessageQueue does not support dialect: {dialectName}')

    async def send_message(self, message: Message, delaySeconds: int = 0) -> None:
        await self.send_messages(messages=[message], delaySeconds=delaySeconds)

    async def send_messages(self, messages: Sequence[Message], delaySeconds: int = 0) -> None:
        if not messages:
            return
        now = self.database.now()
        rows = []
        batchDeduplicationIds: set[str] = set()
        for message in messages:
            message.prepare_for_send()
            if message.deduplicationId is not None:
                if message.deduplicationId in batchDeduplicationIds:
                    continue
                batchDeduplicationIds.add(message.deduplicationId)
            rows.append(
                {
                    'queueName': self.queueName,
                    'command': message.command,
                    'content': message.content,
                    'requestId': message.requestId,
                    'postCount': message.postCount,
                    'postDate': now,
                    'deduplicationId': message.deduplicationId,
                    'status': MESSAGE_STATUS_PENDING,
                    'visibleDate': self.database.now(seconds=delaySeconds),
                    'createdDate': now,
                }
            )
        async with self.database.create_transaction() as connection:
            insertQuery = self._create_insert(dialectName=connection.dialect.name).values(rows)
            earliest = sqlalchemy.func.least if connection.dialect.name == 'postgresql' else sqlalchemy.func.min
            upsertQuery = insertQuery.on_conflict_do_update(
                index_elements=[self.table.c.queueName, self.table.c.deduplicationId], index_where=_PENDING_PREDICATE, set_={self.table.c.visibleDate: earliest(self.table.c.visibleDate, insertQuery.excluded.visibleDate)}
            )
            await self.database.execute(query=upsertQuery, connection=connection)

    async def get_message(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> SqlMessage | None:
        messages = await self.get_messages(limit=1, expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds)
        return messages[0] if messages else None

    async def get_messages(self, limit: int = 1, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> list[SqlMessage]:
        deadline = time.monotonic() + longPollSeconds
        while True:
            messages = await self._claim_messages(limit=limit, expectedProcessingSeconds=expectedProcessingSeconds)
            if messages or time.monotonic() >= deadline:
                return messages
            await asyncio.sleep(min(self.pollIntervalSeconds, max(deadline - time.monotonic(), 0)))

    async def _claim_messages(self, limit: int, expectedProcessingSeconds: int) -> list[SqlMessage]:
        now = self.database.now()
        async with self.database.create_transaction() as connection:
            exhaustedQuery = (
                sqlalchemy.update(self.table)
                .where(self.table.c.queueName == self.queueName)
                .where(self.table.c.status == MESSAGE_STATUS_RUNNING)
                .where(self.table.c.visibleDate <= now)
                .where(self.table.c.postCount >= self.maxAttempts)
                .values(status=MESSAGE_STATUS_FAILED, lockToken=None, completedDate=now, lastError='LEASE_EXPIRED')
            )
            await self.database.execute(query=exhaustedQuery, connection=connection)
            claimableIdsQuery = (
                sqlalchemy.select(self.table.c.id)
                .where(self.table.c.queueName == self.queueName)
                .where(self.table.c.status.in_([MESSAGE_STATUS_PENDING, MESSAGE_STATUS_RUNNING]))
                .where(self.table.c.visibleDate <= now)
                .order_by(self.table.c.visibleDate, self.table.c.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            claimQuery = (
                sqlalchemy.update(self.table)
                .where(self.table.c.id.in_(claimableIdsQuery))
                .values(
                    status=MESSAGE_STATUS_RUNNING,
                    postCount=sqlalchemy.case((self.table.c.status == MESSAGE_STATUS_RUNNING, self.table.c.postCount + 1), else_=self.table.c.postCount),
                    lockToken=str(uuid.uuid4()),
                    owner=self.owner,
                    startedDate=now,
                    visibleDate=self.database.now(seconds=expectedProcessingSeconds),
                )
                .returning(*self.table.c)
            )
            result = await self.database.execute(query=claimQuery, connection=connection)
            rows = result.mappings().all()
        return sorted((SqlMessage.from_row(row=row, table=self.table) for row in rows), key=lambda message: message.id)

    def _owned_update(self, message: SqlMessage) -> sqlalchemy.Update:
        return sqlalchemy.update(self.table).where(self.table.c.id == message.id).where(self.table.c.lockToken == message.lockToken).where(self.table.c.status == MESSAGE_STATUS_RUNNING)

    async def complete_message(self, message: SqlMessage) -> None:
        async with self.database.create_transaction() as connection:
            query = self._owned_update(message=message).values(status=MESSAGE_STATUS_SUCCEEDED, lockToken=None, completedDate=self.database.now())
            await self.database.execute(query=query, connection=connection)

    async def extend_message_lease(self, message: SqlMessage, expectedProcessingSeconds: int) -> bool:
        async with self.database.create_transaction() as connection:
            query = self._owned_update(message=message).values(visibleDate=self.database.now(seconds=expectedProcessingSeconds)).returning(self.table.c.id)
            result = await self.database.execute(query=query, connection=connection)
            return result.first() is not None

    async def retry_message(self, message: SqlMessage, delaySeconds: int = 0) -> None:
        await self._reschedule_message(message=message, delaySeconds=delaySeconds, extraValues={})

    async def fail_message(self, message: SqlMessage, errorMessage: str | None) -> bool:
        postCount = message.postCount or 0
        if postCount >= self.maxAttempts:
            async with self.database.create_transaction() as connection:
                query = self._owned_update(message=message).values(status=MESSAGE_STATUS_FAILED, lockToken=None, completedDate=self.database.now(), lastError=errorMessage)
                await self.database.execute(query=query, connection=connection)
            return False
        await self._reschedule_message(message=message, delaySeconds=self.failureRetryDelaySeconds * postCount, extraValues={'lastError': errorMessage})
        return True

    async def _reschedule_message(self, message: SqlMessage, delaySeconds: float, extraValues: dict[str, Any]) -> None:  # type: ignore[explicit-any]
        async with self.database.create_transaction() as connection:
            try:
                async with connection.begin_nested():
                    query = self._owned_update(message=message).values(status=MESSAGE_STATUS_PENDING, lockToken=None, visibleDate=self.database.now(seconds=delaySeconds), postCount=self.table.c.postCount + 1, postDate=self.database.now(), **extraValues)
                    await self.database.execute(query=query, connection=connection)
            except sqlalchemy.exc.IntegrityError:
                # NOTE(krishan711): an identical message was enqueued while this one ran, so it will do the work instead
                query = self._owned_update(message=message).values(status=MESSAGE_STATUS_DEDUPLICATED, lockToken=None, completedDate=self.database.now())
                await self.database.execute(query=query, connection=connection)

    async def get_message_count(self, shouldSkipRemovingNonRetained: bool = False) -> int:
        countQuery = (
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(self.table)
            .where(self.table.c.queueName == self.queueName)
            .where(self.table.c.status.in_([MESSAGE_STATUS_PENDING, MESSAGE_STATUS_RUNNING]))
            .where(self.table.c.visibleDate <= self.database.now())
        )
        async with self.database.create_transaction() as connection:
            if not shouldSkipRemovingNonRetained:
                deleteQuery = (
                    sqlalchemy.delete(self.table)
                    .where(self.table.c.queueName == self.queueName)
                    .where(self.table.c.status.in_([MESSAGE_STATUS_SUCCEEDED, MESSAGE_STATUS_DEDUPLICATED]))
                    .where(self.table.c.completedDate < self.database.now(seconds=-self.retentionSeconds))
                )
                await self.database.execute(query=deleteQuery, connection=connection)
            result = await self.database.execute(query=countQuery, connection=connection)
        return int(result.scalar_one())

    async def get_inflight_message_count(self) -> int:
        countQuery = sqlalchemy.select(sqlalchemy.func.count()).select_from(self.table).where(self.table.c.queueName == self.queueName).where(self.table.c.status == MESSAGE_STATUS_RUNNING).where(self.table.c.visibleDate > self.database.now())
        async with self.database.create_transaction() as connection:
            result = await self.database.execute(query=countQuery, connection=connection)
        return int(result.scalar_one())
