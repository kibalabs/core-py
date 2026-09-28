import asyncio
import os
import time
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
import sqlalchemy

from core.exceptions import LockedException
from core.locks.model import Lease
from core.locks.sql import LocksMetadata
from core.locks.sql import SqlLock
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
        await connection.run_sync(LocksMetadata.drop_all)
        await connection.run_sync(LocksMetadata.create_all)
    await database.disconnect()
    return connectionString


@pytest_asyncio.fixture
async def workers(connectionString: str) -> AsyncIterator[tuple[SqlLock, SqlLock]]:
    # NOTE: each worker has its own engine so they behave like separate processes
    databases = [Database(connectionString=connectionString) for _ in range(2)]
    for database in databases:
        await database.connect(poolSize=20)
    yield SqlLock(database=databases[0], pollIntervalSeconds=0.05, owner='worker-a'), SqlLock(database=databases[1], pollIntervalSeconds=0.05, owner='worker-b')
    for database in databases:
        await database.disconnect()


async def _expire_lock_row(lock: SqlLock, name: str) -> None:
    async with lock.database.create_transaction() as connection:
        await lock.database.execute(query=sqlalchemy.update(lock.table).where(lock.table.c.name == name).values(expiryDate=date_util.datetime_from_now(seconds=-1)), connection=connection)


async def _count_acquired(results: list[Lease | BaseException]) -> int:
    for result in results:
        if isinstance(result, BaseException) and not isinstance(result, LockedException):
            raise result
    return sum(1 for result in results if isinstance(result, Lease))


async def test_owner_tracks_the_current_holder(workers: tuple[SqlLock, SqlLock]):
    workerA, workerB = workers
    assert await workerB.get_owner(name='job') is None
    lease = await workerA.acquire(name='job')
    assert await workerB.get_owner(name='job') == 'worker-a'
    await workerA.release(lease=lease)
    assert await workerB.get_owner(name='job') is None
    await workerA.acquire(name='job', ttlSeconds=0)
    assert await workerB.get_owner(name='job') is None
    await workerB.acquire(name='job')
    assert await workerA.get_owner(name='job') == 'worker-b'


async def test_locked_exception_names_the_holder(workers: tuple[SqlLock, SqlLock]):
    workerA, workerB = workers
    await workerA.acquire(name='job')
    with pytest.raises(LockedException, match='LOCK_HELD: job by worker-a'):
        await workerB.acquire(name='job')
    with pytest.raises(LockedException, match='LOCK_HELD: job by worker-a'):
        async with workerB.with_lock(name='job'):
            pass


async def test_acquire_is_exclusive_per_name_across_workers(workers: tuple[SqlLock, SqlLock]):
    workerA, workerB = workers
    await workerA.acquire(name='job')
    with pytest.raises(LockedException):
        await workerB.acquire(name='job')
    with pytest.raises(LockedException):
        await workerA.acquire(name='job')
    await workerB.acquire(name='other-job')


async def test_release_frees_the_lock_for_other_workers(workers: tuple[SqlLock, SqlLock]):
    workerA, workerB = workers
    lease = await workerA.acquire(name='job')
    await workerA.release(lease=lease)
    await workerB.acquire(name='job')


async def test_expired_lease_is_taken_over_and_old_holder_can_neither_extend_nor_release(workers: tuple[SqlLock, SqlLock]):
    workerA, workerB = workers
    staleLease = await workerA.acquire(name='job', ttlSeconds=0)
    newLease = await workerB.acquire(name='job')
    assert await workerA.extend(lease=staleLease) is False
    await workerA.release(lease=staleLease)
    with pytest.raises(LockedException):
        await workerA.acquire(name='job')
    assert await workerB.extend(lease=newLease) is True


async def test_expired_lease_cannot_be_extended_even_without_a_takeover(workers: tuple[SqlLock, SqlLock]):
    workerA, _ = workers
    lease = await workerA.acquire(name='job', ttlSeconds=0)
    assert await workerA.extend(lease=lease) is False


async def test_extend_keeps_the_lock_past_its_original_ttl(workers: tuple[SqlLock, SqlLock]):
    workerA, workerB = workers
    lease = await workerA.acquire(name='job', ttlSeconds=1)
    originalExpiryDate = lease.expiryDate
    await asyncio.sleep(0.5)
    assert await workerA.extend(lease=lease, ttlSeconds=2) is True
    assert lease.expiryDate > originalExpiryDate
    await asyncio.sleep(0.8)
    assert lease.is_valid()
    with pytest.raises(LockedException):
        await workerB.acquire(name='job')


async def test_acquire_waits_for_another_worker_to_release(workers: tuple[SqlLock, SqlLock]):
    workerA, workerB = workers
    lease = await workerA.acquire(name='job')

    async def release_later() -> None:
        await asyncio.sleep(0.2)
        await workerA.release(lease=lease)

    releaseTask = asyncio.create_task(release_later())
    await workerB.acquire(name='job', maxWaitSeconds=2)
    await releaseTask


async def test_acquire_takes_over_a_lease_that_expires_while_waiting(workers: tuple[SqlLock, SqlLock]):
    workerA, workerB = workers
    await workerA.acquire(name='job', ttlSeconds=1)
    startTime = time.monotonic()
    await workerB.acquire(name='job', maxWaitSeconds=3)
    assert 0.9 <= time.monotonic() - startTime < 2


async def test_acquire_gives_up_after_max_wait(workers: tuple[SqlLock, SqlLock]):
    workerA, workerB = workers
    await workerA.acquire(name='job')
    startTime = time.monotonic()
    with pytest.raises(LockedException):
        await workerB.acquire(name='job', maxWaitSeconds=0.3)
    assert 0.3 <= time.monotonic() - startTime < 1


async def test_concurrent_acquires_have_exactly_one_winner(workers: tuple[SqlLock, SqlLock]):
    results = await asyncio.gather(*[worker.acquire(name='job') for _ in range(10) for worker in workers], return_exceptions=True)
    assert await _count_acquired(results=results) == 1


async def test_concurrent_takeovers_of_an_expired_lease_have_exactly_one_winner(workers: tuple[SqlLock, SqlLock]):
    workerA, _ = workers
    await workerA.acquire(name='job', ttlSeconds=0)
    results = await asyncio.gather(*[worker.acquire(name='job') for _ in range(10) for worker in workers], return_exceptions=True)
    assert await _count_acquired(results=results) == 1


async def test_with_lock_never_lets_two_workers_in_at_once(workers: tuple[SqlLock, SqlLock]):
    activeCount = 0
    maxActiveCount = 0
    completedCount = 0

    async def run(worker: SqlLock) -> None:
        nonlocal activeCount, maxActiveCount, completedCount
        async with worker.with_lock(name='job', maxWaitSeconds=20):
            activeCount += 1
            maxActiveCount = max(maxActiveCount, activeCount)
            await asyncio.sleep(0.02)
            activeCount -= 1
            completedCount += 1

    await asyncio.gather(*[run(worker=worker) for _ in range(5) for worker in workers])
    assert maxActiveCount == 1
    assert completedCount == 10


async def test_with_lock_releases_when_the_body_raises(workers: tuple[SqlLock, SqlLock]):
    workerA, workerB = workers
    with pytest.raises(ValueError, match='boom'):
        async with workerA.with_lock(name='job'):
            raise ValueError('boom')
    await workerB.acquire(name='job')


async def test_with_lock_raises_when_held_and_leaves_the_holder_untouched(workers: tuple[SqlLock, SqlLock]):
    workerA, workerB = workers
    lease = await workerA.acquire(name='job')
    with pytest.raises(LockedException):
        async with workerB.with_lock(name='job'):
            pytest.fail('body must not run without the lock')
    assert await workerA.extend(lease=lease) is True


async def test_with_lock_keeps_the_lease_alive_past_its_ttl(workers: tuple[SqlLock, SqlLock]):
    workerA, workerB = workers
    async with workerA.with_lock(name='job', ttlSeconds=1) as lease:
        await asyncio.sleep(1.5)
        assert lease.is_valid()
        with pytest.raises(LockedException):
            await workerB.acquire(name='job')


async def test_with_lock_marks_the_lease_lost_after_a_takeover_and_does_not_release_the_new_holder(workers: tuple[SqlLock, SqlLock]):
    workerA, workerB = workers
    async with workerA.with_lock(name='job', ttlSeconds=1) as lease:
        await _expire_lock_row(lock=workerA, name='job')
        newLease = await workerB.acquire(name='job')
        await asyncio.sleep(0.6)
        assert lease.isLost
        assert not lease.is_valid()
    assert await workerB.extend(lease=newLease) is True


async def test_with_lock_keep_alive_survives_a_transient_extend_failure(workers: tuple[SqlLock, SqlLock]):
    workerA, workerB = workers

    class FlakyLock(SqlLock):
        extendCallCount = 0

        async def extend(self, lease: Lease, ttlSeconds: int = 60) -> bool:
            self.extendCallCount += 1
            if self.extendCallCount == 1:
                raise ConnectionError('transient')
            return await super().extend(lease=lease, ttlSeconds=ttlSeconds)

    flakyLock = FlakyLock(database=workerA.database, pollIntervalSeconds=0.05)
    async with flakyLock.with_lock(name='job', ttlSeconds=1) as lease:
        await asyncio.sleep(1.5)
        assert flakyLock.extendCallCount >= 2
        assert lease.is_valid()
        with pytest.raises(LockedException):
            await workerB.acquire(name='job')


async def test_lock_changes_commit_independently_of_the_callers_transaction(workers: tuple[SqlLock, SqlLock]):
    workerA, workerB = workers
    with pytest.raises(ValueError, match='rollback'):
        async with workerA.database.create_context_connection():
            await workerA.acquire(name='job')
            with pytest.raises(LockedException):
                await workerB.acquire(name='job')
            raise ValueError('rollback')
    with pytest.raises(LockedException):
        await workerB.acquire(name='job')
