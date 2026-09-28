import abc
import asyncio
import contextlib
from abc import ABC
from collections.abc import AsyncIterator

from core import logging
from core.exceptions import LockedException
from core.locks.model import LockLease


class Lock(ABC):
    @abc.abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def disconnect(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def acquire(self, name: str, ttlSeconds: int = 60, maxWaitSeconds: float = 0) -> LockLease:
        raise NotImplementedError

    @abc.abstractmethod
    async def extend(self, lease: LockLease, ttlSeconds: int = 60) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    async def release(self, lease: LockLease) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_owner(self, name: str) -> str | None:
        raise NotImplementedError

    async def ensure_held(self, lease: LockLease) -> None:
        if lease.isLost or not await self.extend(lease=lease, ttlSeconds=lease.ttlSeconds):
            lease.isLost = True
            raise LockedException(message=f'LOCK_LOST: {lease.name}')

    async def _keep_alive(self, lease: LockLease) -> None:
        while True:
            await asyncio.sleep(lease.ttlSeconds / 3)
            try:
                isExtended = await self.extend(lease=lease, ttlSeconds=lease.ttlSeconds)
            except Exception as exception:  # noqa: BLE001
                # NOTE(krishan711): a transient failure must not kill the keep-alive; the lease simply lapses at expiryDate if it keeps failing
                logging.error(f'Failed to extend lease {lease.name}:')
                logging.exception(exception)
                continue
            if not isExtended:
                lease.isLost = True
                logging.error(f'Lost lease {lease.name}')
                return

    @contextlib.asynccontextmanager
    async def with_lock(self, name: str, ttlSeconds: int = 60, maxWaitSeconds: float = 0) -> AsyncIterator[LockLease]:
        lease = await self.acquire(name=name, ttlSeconds=ttlSeconds, maxWaitSeconds=maxWaitSeconds)
        keepAliveTask = asyncio.create_task(self._keep_alive(lease=lease))
        try:
            yield lease
        finally:
            keepAliveTask.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await keepAliveTask
            await self.release(lease=lease)
