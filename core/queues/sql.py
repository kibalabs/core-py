from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Any

import sqlalchemy
from sqlalchemy.dialects import postgresql as sqlalchemy_psql

from core.queues.message_queue import MessageQueue
from core.queues.model import Message
from core.store.database import Database
from core.util import date_util

# NOTE: this table is owned here (not in the consuming app's schema.py) so it can ship with
# core-py. To include it in an app's own alembic-tracked metadata (so autogenerate creates the
# table), call `QueueMessagesTable.to_metadata(appMetadata)` from the app's schema module.
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
    sqlalchemy.Column(key='lockToken', name='lock_token', type_=sqlalchemy.Text, nullable=True),
    sqlalchemy.Column(key='visibleDate', name='visible_date', type_=sqlalchemy.DateTime(timezone=True), nullable=False, index=True),
    sqlalchemy.UniqueConstraint('queueName', 'deduplicationId', name='tbl_queue_messages_ux_queue_name_deduplication_id'),
)


class SqlMessage(Message):
    id: int
    lockToken: str

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> SqlMessage:  # type: ignore[explicit-any]
        return cls(
            id=row['id'],
            command=row['command'],
            content=row['content'],
            requestId=row['request_id'],
            postCount=row['post_count'],
            postDate=row['post_date'],
            deduplicationId=row['deduplication_id'],
            lockToken=row['lock_token'],
        )


class SqlMessageQueue(MessageQueue[SqlMessage]):
    def __init__(self, database: Database, queueName: str, table: sqlalchemy.Table = QueueMessagesTable, pollIntervalSeconds: float = 1.0) -> None:
        self.database = database
        self.queueName = queueName
        self.table = table
        self.pollIntervalSeconds = pollIntervalSeconds

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def send_message(self, message: Message, delaySeconds: int = 0) -> None:
        await self.send_messages(messages=[message], delaySeconds=delaySeconds)

    async def send_messages(self, messages: Sequence[Message], delaySeconds: int = 0) -> None:
        if not messages:
            return
        now = date_util.datetime_from_now()
        visibleDate = date_util.datetime_from_now(seconds=delaySeconds)
        async with self.database.create_transaction() as connection:
            for message in messages:
                message.prepare_for_send()
                insertQuery = self.table.insert().values(
                    queueName=self.queueName,
                    command=message.command,
                    content=message.content,
                    requestId=message.requestId,
                    postCount=message.postCount,
                    postDate=message.postDate,
                    deduplicationId=message.deduplicationId,
                    lockToken=None,
                    visibleDate=visibleDate,
                    createdDate=now,
                )
                if message.deduplicationId is not None:
                    # A message with the same (queueName, deduplicationId) may already be queued;
                    # the unique constraint on those columns rejects it. Use a SAVEPOINT so that
                    # failure only rolls back this one insert, not the whole batch's transaction.
                    try:
                        async with connection.begin_nested():
                            await self.database.execute(query=insertQuery, connection=connection)  # type: ignore[arg-type]
                    except sqlalchemy.exc.IntegrityError:
                        pass
                else:
                    await self.database.execute(query=insertQuery, connection=connection)  # type: ignore[arg-type]

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
        newVisibleDate = date_util.datetime_from_now(seconds=expectedProcessingSeconds)
        async with self.database.create_transaction() as connection:
            selectQuery = sqlalchemy.select(self.table).where(self.table.c.queueName == self.queueName).where(self.table.c.visibleDate <= now).order_by(self.table.c.id).limit(limit).with_for_update(skip_locked=True)
            result = await self.database.execute(query=selectQuery, connection=connection)
            rows = result.mappings().all()
            messages: list[SqlMessage] = []
            for row in rows:
                lockToken = str(uuid.uuid4())
                updateQuery = sqlalchemy.update(self.table).where(self.table.c.id == row['id']).values(lockToken=lockToken, visibleDate=newVisibleDate)
                await self.database.execute(query=updateQuery, connection=connection)  # type: ignore[arg-type]
                messages.append(SqlMessage.from_row(row={**row, 'lock_token': lockToken}))
            return messages

    async def delete_message(self, message: SqlMessage) -> None:
        async with self.database.create_transaction() as connection:
            deleteQuery = sqlalchemy.delete(self.table).where(self.table.c.id == message.id).where(self.table.c.lockToken == message.lockToken)
            await self.database.execute(query=deleteQuery, connection=connection)  # type: ignore[arg-type]
