import asyncio
import time
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from core.exceptions import LockedException
from core.locks.sql import LocksMetadata
from core.locks.sql import SqlLock
from core.store.database import Database


@pytest_asyncio.fixture
async def lock(tmp_path) -> AsyncIterator[SqlLock]:
    database = Database(connectionString=Database.create_sqlite_connection_string(str(tmp_path / 'database.sqlite')))
    await database.connect(poolSize=1)
    async with database.create_transaction() as connection:
        await connection.run_sync(LocksMetadata.create_all)
    yield SqlLock(database=database, pollIntervalSeconds=0.05)
    await database.disconnect()


@pytest.mark.asyncio
async def test_acquire_is_exclusive_until_released(lock: SqlLock):
    lease = await lock.acquire(name='job')
    with pytest.raises(LockedException):
        await lock.acquire(name='job')
    await lock.acquire(name='other-job')
    await lock.release(lease=lease)
    await lock.acquire(name='job')


@pytest.mark.asyncio
async def test_expired_lease_can_be_taken_over_and_old_holder_loses_it(lock: SqlLock):
    staleLease = await lock.acquire(name='job', ttlSeconds=0)
    newLease = await lock.acquire(name='job')
    assert await lock.extend(lease=staleLease) is False
    await lock.release(lease=staleLease)
    with pytest.raises(LockedException):
        await lock.acquire(name='job')
    assert await lock.extend(lease=newLease) is True


@pytest.mark.asyncio
async def test_acquire_waits_for_release(lock: SqlLock):
    lease = await lock.acquire(name='job')

    async def release_later() -> None:
        await asyncio.sleep(0.1)
        await lock.release(lease=lease)

    releaseTask = asyncio.create_task(release_later())
    await lock.acquire(name='job', maxWaitSeconds=2)
    await releaseTask


@pytest.mark.asyncio
async def test_acquire_gives_up_after_max_wait(lock: SqlLock):
    await lock.acquire(name='job')
    startTime = time.monotonic()
    with pytest.raises(LockedException):
        await lock.acquire(name='job', maxWaitSeconds=0.3)
    assert 0.3 <= time.monotonic() - startTime < 1


@pytest.mark.asyncio
async def test_with_lock_raises_when_held_and_releases_on_exit(lock: SqlLock):
    with pytest.raises(ValueError, match='boom'):
        async with lock.with_lock(name='job'):
            with pytest.raises(LockedException):
                async with lock.with_lock(name='job'):
                    pass
            raise ValueError('boom')
    await lock.acquire(name='job')


@pytest.mark.asyncio
async def test_with_lock_keeps_lease_alive_past_ttl(lock: SqlLock):
    async with lock.with_lock(name='job', ttlSeconds=1) as lease:
        await asyncio.sleep(1.5)
        assert lease.is_valid()
        with pytest.raises(LockedException):
            await lock.acquire(name='job')
