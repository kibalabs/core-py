import asyncio

import pytest

from core.queues.message_queue_processor import MessageProcessor
from core.queues.message_queue_processor import MessageQueueProcessor
from core.queues.model import Message


class EmptyQueue:
    async def get_messages(self, expectedProcessingSeconds: int, longPollSeconds: int, limit: int) -> list[Message]:  # noqa: ARG002
        return []


class NoopProcessor(MessageProcessor):
    async def process_message(self, message: Message) -> None:
        pass


def _processor(pollLogIntervalSeconds: float) -> MessageQueueProcessor[Message]:
    return MessageQueueProcessor(queue=EmptyQueue(), messageProcessor=NoopProcessor(), notificationClients=[], pollLogIntervalSeconds=pollLogIntervalSeconds)  # type: ignore[arg-type]


def _pollLogCount(caplog: pytest.LogCaptureFixture) -> int:
    return sum(1 for record in caplog.records if record.getMessage() == 'Retrieving messages...')


@pytest.mark.asyncio
async def test_poll_is_logged_once_per_interval(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level('INFO')
    processor = _processor(pollLogIntervalSeconds=0.2)
    await processor.execute_batch(batchSize=1)
    await processor.execute_batch(batchSize=1)
    assert _pollLogCount(caplog) == 1
    await asyncio.sleep(0.25)
    await processor.execute_batch(batchSize=1)
    assert _pollLogCount(caplog) == 2  # noqa: PLR2004


@pytest.mark.asyncio
async def test_zero_interval_logs_every_poll(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level('INFO')
    processor = _processor(pollLogIntervalSeconds=0)
    for _ in range(3):
        await processor.execute_batch(batchSize=1)
    assert _pollLogCount(caplog) == 3  # noqa: PLR2004
