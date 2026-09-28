from __future__ import annotations

import asyncio
import datetime
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
from core.util import date_util
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
    sqlalchemy.Column(key='postCount', name='post_count', type_=sqlalchemy.Integer, nullable=True),
    sqlalchemy.Column(key='postDate', name='post_date', type_=sqlalchemy.DateTime(timezone=True), nullable=True),
    sqlalchemy.Column(key='deduplicationId', name='deduplication_id', type_=sqlalchemy.Text, nullable=True),
    sqlalchemy.Column(key='status', name='status', type_=sqlalchemy.Text, nullable=False),
    sqlalchemy.Column(key='visibleDate', name='visible_date', type_=sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column(key='attemptCount', name='attempt_count', type_=sqlalchemy.Integer, nullable=False),
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
    attemptCount: int

    @staticmethod
    def _get_row_value(row: RowMapping, key: str, databaseKey: str) -> Any:  # type: ignore[explicit-any]
        if key in row:
            return row[key]
        return row[databaseKey]

    @classmethod
    def from_row(cls, row: RowMapping) -> SqlMessage:
        return cls(
            id=cls._get_row_value(row, 'id', 'id'),
            command=cls._get_row_value(row, 'command', 'command'),
            content=cls._get_row_value(row, 'content', 'content'),
            requestId=cls._get_row_value(row, 'requestId', 'request_id'),
            postCount=cls._get_row_value(row, 'postCount', 'post_count'),
            postDate=cls._get_row_value(row, 'postDate', 'post_date'),
            deduplicationId=cls._get_row_value(row, 'deduplicationId', 'deduplication_id'),
            lockToken=cls._get_row_value(row, 'lockToken', 'lock_token'),
            attemptCount=cls._get_row_value(row, 'attemptCount', 'attempt_count'),
        )


class SqlMessageQueue(MessageQueue[SqlMessage]):
    def __init__(
        self,
        database: Database,
        queueName: str,
        table: sqlalchemy.Table = QueueMessagesTable,
        pollIntervalSeconds: float = 1.0,
        maxAttempts: int = 3,
        failureRetryDelaySeconds: int = 60,
        owner: str | None = None,
    ) -> None:
        self.database = database
        self.queueName = queueName
        self.table = table
        self.pollIntervalSeconds = pollIntervalSeconds
        self.maxAttempts = maxAttempts
        self.failureRetryDelaySeconds = failureRetryDelaySeconds
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
        now = date_util.datetime_from_now()
        visibleDate = date_util.datetime_from_now(seconds=delaySeconds)
        rows = []
        for message in messages:
            message.prepare_for_send()
            rows.append(
                {
                    'queueName': self.queueName,
                    'command': message.command,
                    'content': message.content,
                    'requestId': message.requestId,
                    'postCount': message.postCount,
                    'postDate': message.postDate,
                    'deduplicationId': message.deduplicationId,
                    'status': MESSAGE_STATUS_PENDING,
                    'visibleDate': visibleDate,
                    'attemptCount': 0,
                    'createdDate': now,
                }
            )
        async with self.database.create_transaction() as connection:
            insertQuery = self._create_insert(dialectName=connection.dialect.name).values(rows).on_conflict_do_nothing(index_elements=[self.table.c.queueName, self.table.c.deduplicationId], index_where=_PENDING_PREDICATE)
            await self.database.execute(query=insertQuery, connection=connection)

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
        now = date_util.datetime_from_now()
        async with self.database.create_transaction() as connection:
            exhaustedQuery = (
                sqlalchemy.update(self.table)
                .where(self.table.c.queueName == self.queueName)
                .where(self.table.c.status == MESSAGE_STATUS_RUNNING)
                .where(self.table.c.visibleDate <= now)
                .where(self.table.c.attemptCount >= self.maxAttempts)
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
                    attemptCount=self.table.c.attemptCount + 1,
                    lockToken=str(uuid.uuid4()),
                    owner=self.owner,
                    startedDate=now,
                    visibleDate=date_util.datetime_from_now(seconds=expectedProcessingSeconds),
                )
                .returning(*self.table.c)
            )
            result = await self.database.execute(query=claimQuery, connection=connection)
            rows = result.mappings().all()
        return sorted((SqlMessage.from_row(row=row) for row in rows), key=lambda message: message.id)

    def _owned_update(self, message: SqlMessage) -> sqlalchemy.Update:
        return sqlalchemy.update(self.table).where(self.table.c.id == message.id).where(self.table.c.lockToken == message.lockToken).where(self.table.c.status == MESSAGE_STATUS_RUNNING)

    async def complete_message(self, message: SqlMessage) -> None:
        async with self.database.create_transaction() as connection:
            query = self._owned_update(message=message).values(status=MESSAGE_STATUS_SUCCEEDED, lockToken=None, completedDate=date_util.datetime_from_now())
            await self.database.execute(query=query, connection=connection)

    async def retry_message(self, message: SqlMessage, delaySeconds: int = 0) -> None:
        now = date_util.datetime_from_now()
        await self._reschedule_message(message=message, visibleDate=date_util.datetime_from_now(seconds=delaySeconds), extraValues={'postCount': self.table.c.postCount + 1, 'postDate': now})

    async def fail_message(self, message: SqlMessage, errorMessage: str | None) -> None:
        if message.attemptCount >= self.maxAttempts:
            async with self.database.create_transaction() as connection:
                query = self._owned_update(message=message).values(status=MESSAGE_STATUS_FAILED, lockToken=None, completedDate=date_util.datetime_from_now(), lastError=errorMessage)
                await self.database.execute(query=query, connection=connection)
            return
        visibleDate = date_util.datetime_from_now(seconds=self.failureRetryDelaySeconds * message.attemptCount)
        await self._reschedule_message(message=message, visibleDate=visibleDate, extraValues={'lastError': errorMessage})

    async def _reschedule_message(self, message: SqlMessage, visibleDate: datetime.datetime, extraValues: dict[str, Any]) -> None:  # type: ignore[explicit-any]
        async with self.database.create_transaction() as connection:
            try:
                async with connection.begin_nested():
                    query = self._owned_update(message=message).values(status=MESSAGE_STATUS_PENDING, lockToken=None, visibleDate=visibleDate, **extraValues)
                    await self.database.execute(query=query, connection=connection)
            except sqlalchemy.exc.IntegrityError:
                # NOTE(krishan711): an identical message was enqueued while this one ran, so it will do the work instead
                query = self._owned_update(message=message).values(status=MESSAGE_STATUS_DEDUPLICATED, lockToken=None, completedDate=date_util.datetime_from_now())
                await self.database.execute(query=query, connection=connection)

    async def delete_completed_messages(self, retentionSeconds: int) -> int:
        async with self.database.create_transaction() as connection:
            query = (
                sqlalchemy.delete(self.table)
                .where(self.table.c.queueName == self.queueName)
                .where(self.table.c.status.in_([MESSAGE_STATUS_SUCCEEDED, MESSAGE_STATUS_DEDUPLICATED]))
                .where(self.table.c.completedDate < date_util.datetime_from_now(seconds=-retentionSeconds))
                .returning(self.table.c.id)
            )
            result = await self.database.execute(query=query, connection=connection)
            return len(result.all())

    async def get_message_count(self) -> int:
        countQuery = (
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(self.table)
            .where(self.table.c.queueName == self.queueName)
            .where(self.table.c.status.in_([MESSAGE_STATUS_PENDING, MESSAGE_STATUS_RUNNING]))
            .where(self.table.c.visibleDate <= date_util.datetime_from_now())
        )
        async with self.database.create_transaction() as connection:
            result = await self.database.execute(query=countQuery, connection=connection)
        return int(result.scalar_one())

    async def get_inflight_message_count(self) -> int:
        countQuery = (
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(self.table)
            .where(self.table.c.queueName == self.queueName)
            .where(self.table.c.status == MESSAGE_STATUS_RUNNING)
            .where(self.table.c.visibleDate > date_util.datetime_from_now())
        )
        async with self.database.create_transaction() as connection:
            result = await self.database.execute(query=countQuery, connection=connection)
        return int(result.scalar_one())
