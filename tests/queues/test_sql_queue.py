import asyncio
import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
import sqlalchemy

from core.exceptions import LockedException
from core.queues.message_queue_processor import MessageNeedsReprocessingException
from core.queues.message_queue_processor import MessageProcessor
from core.queues.message_queue_processor import MessageQueueProcessor
from core.queues.model import Message
from core.queues.sql import QueueMessagesMetadata
from core.queues.sql import SqlMessage
from core.queues.sql import SqlMessageQueue
from core.store.database import Database
from core.util import date_util

PSQL_CONNECTION_STRING = os.environ.get('CORE_TEST_PSQL_CONNECTION_STRING')

pytestmark = pytest.mark.asyncio


# NOTE: postgres only runs when a connection string is given; skipping it instead breaks kiba-build's test-check report parsing
@pytest_asyncio.fixture(params=['sqlite', 'postgresql'] if PSQL_CONNECTION_STRING else ['sqlite'])
async def connectionString(request, tmp_path) -> str:
    connectionString = PSQL_CONNECTION_STRING if request.param == 'postgresql' else Database.create_sqlite_connection_string(str(tmp_path / 'database.sqlite'))
    database = Database(connectionString=connectionString)
    await database.connect(poolSize=1)
    async with database.create_transaction() as connection:
        await connection.run_sync(QueueMessagesMetadata.drop_all)
        await connection.run_sync(QueueMessagesMetadata.create_all)
    await database.disconnect()
    return connectionString


@pytest_asyncio.fixture
async def workers(connectionString: str) -> AsyncIterator[tuple[SqlMessageQueue, SqlMessageQueue]]:
    # NOTE: each worker has its own engine so they behave like separate processes
    databases = [Database(connectionString=connectionString) for _ in range(2)]
    for database in databases:
        await database.connect(poolSize=20)
    yield (
        SqlMessageQueue(database=databases[0], queueName='work', pollIntervalSeconds=0.05, maxAttempts=3, failureRetryDelaySeconds=60, owner='worker-a'),
        SqlMessageQueue(database=databases[1], queueName='work', pollIntervalSeconds=0.05, maxAttempts=3, failureRetryDelaySeconds=60, owner='worker-b'),
    )
    for database in databases:
        await database.disconnect()


def _message(deduplicationId: str | None = 'dedup', userId: str = 'user-1') -> Message:
    return Message(command='DO_WORK', content={'userId': userId}, requestId=None, postCount=None, postDate=None, deduplicationId=deduplicationId)


async def _rows(queue: SqlMessageQueue) -> list[dict[str, Any]]:  # type: ignore[explicit-any]
    async with queue.database.create_transaction() as connection:
        result = await queue.database.execute(query=sqlalchemy.select(queue.table).order_by(queue.table.c.id), connection=connection)
    return [dict(row) for row in result.mappings().all()]


async def _row(queue: SqlMessageQueue, messageId: int) -> dict[str, Any]:  # type: ignore[explicit-any]
    return next(row for row in await _rows(queue=queue) if row['id'] == messageId)


async def _make_visible(queue: SqlMessageQueue, messageId: int) -> None:
    async with queue.database.create_transaction() as connection:
        await queue.database.execute(query=sqlalchemy.update(queue.table).where(queue.table.c.id == messageId).values(visibleDate=date_util.datetime_from_now(seconds=-1)), connection=connection)


async def _claim(queue: SqlMessageQueue) -> SqlMessage:
    message = await queue.get_message()
    assert message is not None
    return message


async def test_identical_pending_messages_are_deduplicated(workers: tuple[SqlMessageQueue, SqlMessageQueue]):
    workerA, _ = workers
    await workerA.send_message(message=_message())
    await workerA.send_messages(messages=[_message(), _message()])
    assert len(await _rows(queue=workerA)) == 1


async def test_messages_without_deduplication_id_are_all_kept(workers: tuple[SqlMessageQueue, SqlMessageQueue]):
    workerA, _ = workers
    await workerA.send_messages(messages=[_message(deduplicationId=None), _message(deduplicationId=None)])
    assert len(await _rows(queue=workerA)) == 2  # noqa: PLR2004


async def test_identical_message_is_queued_while_the_original_runs(workers: tuple[SqlMessageQueue, SqlMessageQueue]):
    workerA, _ = workers
    await workerA.send_message(message=_message())
    await _claim(queue=workerA)
    await workerA.send_message(message=_message())
    assert [row['status'] for row in await _rows(queue=workerA)] == ['running', 'pending']


async def test_delayed_message_is_not_claimed_until_visible(workers: tuple[SqlMessageQueue, SqlMessageQueue]):
    workerA, _ = workers
    await workerA.send_message(message=_message(), delaySeconds=60)
    assert await workerA.get_message() is None
    assert await workerA.get_message_count() == 0


async def test_concurrent_claims_never_hand_out_the_same_message(workers: tuple[SqlMessageQueue, SqlMessageQueue]):
    await workers[0].send_messages(messages=[_message(deduplicationId=None, userId=str(index)) for index in range(20)])
    results = await asyncio.gather(*[worker.get_messages(limit=3) for _ in range(5) for worker in workers])
    claimedIds = [message.id for messages in results for message in messages]
    assert len(claimedIds) == len(set(claimedIds)) == 20  # noqa: PLR2004


async def test_completed_message_is_kept_as_succeeded_and_not_reclaimed(workers: tuple[SqlMessageQueue, SqlMessageQueue]):
    workerA, workerB = workers
    await workerA.send_message(message=_message())
    message = await _claim(queue=workerA)
    await workerA.complete_message(message=message)
    row = await _row(queue=workerA, messageId=message.id)
    assert row['status'] == 'succeeded'
    assert row['owner'] == 'worker-a'
    assert row['completed_date'] is not None
    await _make_visible(queue=workerA, messageId=message.id)
    assert await workerB.get_message() is None


async def test_expired_lease_is_reclaimed_and_old_holder_cannot_complete(workers: tuple[SqlMessageQueue, SqlMessageQueue]):
    workerA, workerB = workers
    await workerA.send_message(message=_message())
    staleMessage = await _claim(queue=workerA)
    await _make_visible(queue=workerA, messageId=staleMessage.id)
    newMessage = await _claim(queue=workerB)
    assert newMessage.id == staleMessage.id
    assert newMessage.postCount == 2  # noqa: PLR2004
    await workerA.complete_message(message=staleMessage)
    assert (await _row(queue=workerA, messageId=staleMessage.id))['status'] == 'running'
    await workerB.complete_message(message=newMessage)
    assert (await _row(queue=workerA, messageId=staleMessage.id))['status'] == 'succeeded'


async def test_expired_lease_with_no_attempts_left_is_failed(workers: tuple[SqlMessageQueue, SqlMessageQueue]):
    workerA, _ = workers
    await workerA.send_message(message=_message())
    for _ in range(3):
        message = await _claim(queue=workerA)
        await _make_visible(queue=workerA, messageId=message.id)
    assert await workerA.get_message() is None
    row = await _row(queue=workerA, messageId=message.id)
    assert row['status'] == 'failed'
    assert row['last_error'] == 'LEASE_EXPIRED'


async def test_failed_message_backs_off_then_fails_after_max_attempts(workers: tuple[SqlMessageQueue, SqlMessageQueue]):
    workerA, _ = workers
    await workerA.send_message(message=_message())
    for attempt in range(1, 4):
        message = await _claim(queue=workerA)
        assert message.postCount == attempt
        await workerA.fail_message(message=message, errorMessage=f'boom {attempt}')
        row = await _row(queue=workerA, messageId=message.id)
        if attempt < 3:  # noqa: PLR2004
            assert row['status'] == 'pending'
            assert await workerA.get_message() is None
            await _make_visible(queue=workerA, messageId=message.id)
    assert row['status'] == 'failed'
    assert row['last_error'] == 'boom 3'
    await _make_visible(queue=workerA, messageId=message.id)
    assert await workerA.get_message() is None


async def test_retry_reschedules_the_same_message_with_a_delay(workers: tuple[SqlMessageQueue, SqlMessageQueue]):
    workerA, _ = workers
    await workerA.send_message(message=_message())
    message = await _claim(queue=workerA)
    await workerA.retry_message(message=message, delaySeconds=60)
    assert await workerA.get_message() is None
    await _make_visible(queue=workerA, messageId=message.id)
    retriedMessage = await _claim(queue=workerA)
    assert retriedMessage.id == message.id
    assert retriedMessage.postCount == 2  # noqa: PLR2004
    assert len(await _rows(queue=workerA)) == 1


async def test_retry_is_folded_into_an_identical_pending_message(workers: tuple[SqlMessageQueue, SqlMessageQueue]):
    workerA, _ = workers
    await workerA.send_message(message=_message())
    message = await _claim(queue=workerA)
    await workerA.send_message(message=_message())
    await workerA.retry_message(message=message)
    assert [row['status'] for row in await _rows(queue=workerA)] == ['deduplicated', 'pending']


async def test_message_count_removes_only_old_finished_messages_unless_skipped(workers: tuple[SqlMessageQueue, SqlMessageQueue]):
    workerA, _ = workers
    await workerA.send_messages(messages=[_message(deduplicationId=None, userId=str(index)) for index in range(4)])
    succeededMessage, failedMessage, recentMessage = await workerA.get_messages(limit=3)
    await workerA.complete_message(message=succeededMessage)
    await SqlMessageQueue(database=workerA.database, queueName='work', maxAttempts=1).fail_message(message=failedMessage, errorMessage='boom')
    await workerA.complete_message(message=recentMessage)
    async with workerA.database.create_transaction() as connection:
        await workerA.database.execute(query=sqlalchemy.update(workerA.table).where(workerA.table.c.id.in_([succeededMessage.id, failedMessage.id])).values(completedDate=date_util.datetime_from_now(days=-8)), connection=connection)
    assert await workerA.get_message_count(shouldSkipRemovingNonRetained=True) == 1
    assert len(await _rows(queue=workerA)) == 4  # noqa: PLR2004
    assert await workerA.get_message_count() == 1
    assert [row['status'] for row in await _rows(queue=workerA)] == ['failed', 'succeeded', 'pending']


async def test_counts_split_waiting_and_inflight(workers: tuple[SqlMessageQueue, SqlMessageQueue]):
    workerA, _ = workers
    await workerA.send_messages(messages=[_message(deduplicationId=None, userId=str(index)) for index in range(3)])
    await workerA.send_message(message=_message(deduplicationId=None), delaySeconds=60)
    await _claim(queue=workerA)
    assert await workerA.get_message_count() == 2  # noqa: PLR2004
    assert await workerA.get_inflight_message_count() == 1


async def test_processor_always_retries_reprocessing_messages(workers: tuple[SqlMessageQueue, SqlMessageQueue]):
    workerA, _ = workers

    class ReprocessingProcessor(MessageProcessor):
        async def process_message(self, message: Message) -> None:
            raise MessageNeedsReprocessingException(delaySeconds=30)

    processor = MessageQueueProcessor(queue=workerA, messageProcessor=ReprocessingProcessor(), notificationClients=[])
    await workerA.send_message(message=_message())
    for _ in range(6):
        assert await processor.execute(longPollSeconds=0)
        row = (await _rows(queue=workerA))[0]
        assert row['status'] == 'pending'
        assert await workerA.get_message() is None
        await _make_visible(queue=workerA, messageId=row['id'])


async def test_processor_retries_locked_messages_three_times_then_fails_them(workers: tuple[SqlMessageQueue, SqlMessageQueue]):
    workerA, _ = workers

    class LockHeldProcessor(MessageProcessor):
        async def process_message(self, message: Message) -> None:
            raise LockedException(message='LOCK_HELD: job by worker-b')

    processor = MessageQueueProcessor(queue=workerA, messageProcessor=LockHeldProcessor(), notificationClients=[])
    await workerA.send_message(message=_message())
    for _ in range(3):
        assert await processor.execute(longPollSeconds=0)
        row = (await _rows(queue=workerA))[0]
        assert row['status'] == 'pending'
        assert await workerA.get_message() is None
        await _make_visible(queue=workerA, messageId=row['id'])
    assert await processor.execute(longPollSeconds=0)
    row = (await _rows(queue=workerA))[0]
    assert row['status'] == 'failed'
    assert row['last_error'] == 'LOCK_HELD: job by worker-b'
