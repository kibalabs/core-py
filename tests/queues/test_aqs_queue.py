import asyncio
import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from azure.storage.queue.aio import QueueClient

from core.queues.aqs import AqsMessage
from core.queues.aqs import AqsMessageQueue
from core.queues.model import Message

AQS_ENDPOINT = os.environ['CORE_TEST_AQS_ENDPOINT']
# NOTE: the public, fixed account every azurite emulator uses
AZURITE_ACCOUNT_NAME = 'devstoreaccount1'
AZURITE_ACCOUNT_KEY = 'Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=='

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def workers() -> AsyncIterator[tuple[AqsMessageQueue, AqsMessageQueue]]:
    queueName = f'test-{uuid.uuid4().hex}'
    connectionString = f'DefaultEndpointsProtocol=http;AccountName={AZURITE_ACCOUNT_NAME};AccountKey={AZURITE_ACCOUNT_KEY};QueueEndpoint={AQS_ENDPOINT}'
    async with QueueClient.from_connection_string(conn_str=connectionString, queue_name=queueName) as client:
        await client.create_queue()
    queues = [AqsMessageQueue(storageAccountName=AZURITE_ACCOUNT_NAME, storageAccountKey=AZURITE_ACCOUNT_KEY, queueName=queueName, endpointUrl=AQS_ENDPOINT) for _ in range(2)]
    for queue in queues:
        await queue.connect()
    yield queues[0], queues[1]
    for queue in queues:
        await queue.disconnect()


def _message() -> Message:
    return Message(command='DO_WORK', content={'userId': 'user-1'}, requestId=None, postCount=None, postDate=None, deduplicationId=None)


async def _claim(queue: AqsMessageQueue, expectedProcessingSeconds: int = 300) -> AqsMessage:
    message = await queue.get_message(expectedProcessingSeconds=expectedProcessingSeconds)
    assert message is not None
    return message


async def test_extended_message_stays_invisible_and_can_still_be_completed(workers: tuple[AqsMessageQueue, AqsMessageQueue]):
    workerA, workerB = workers
    await workerA.send_message(message=_message())
    message = await _claim(queue=workerA, expectedProcessingSeconds=1)
    assert await workerA.extend_message_lease(message=message, expectedProcessingSeconds=60) is True
    await asyncio.sleep(1.5)
    assert await workerB.get_message() is None
    await workerA.complete_message(message=message)
    assert await workerA.get_message_count() == 0


async def test_extend_after_another_worker_received_the_message_reports_the_lease_lost(workers: tuple[AqsMessageQueue, AqsMessageQueue]):
    workerA, workerB = workers
    await workerA.send_message(message=_message())
    staleMessage = await _claim(queue=workerA, expectedProcessingSeconds=1)
    await asyncio.sleep(1.5)
    await _claim(queue=workerB)
    assert await workerA.extend_message_lease(message=staleMessage, expectedProcessingSeconds=60) is False


async def test_retry_after_losing_the_lease_does_not_duplicate_the_message(workers: tuple[AqsMessageQueue, AqsMessageQueue]):
    workerA, workerB = workers
    await workerA.send_message(message=_message())
    staleMessage = await _claim(queue=workerA, expectedProcessingSeconds=1)
    await asyncio.sleep(1.5)
    newMessage = await _claim(queue=workerB)
    await workerA.retry_message(message=staleMessage)
    await workerB.complete_message(message=newMessage)
    assert await workerA.get_message() is None


async def test_retry_reschedules_without_leaving_the_original_behind(workers: tuple[AqsMessageQueue, AqsMessageQueue]):
    workerA, _ = workers
    await workerA.send_message(message=_message())
    await workerA.retry_message(message=await _claim(queue=workerA, expectedProcessingSeconds=1))
    retriedMessage = await _claim(queue=workerA)
    assert retriedMessage.postCount == 2  # noqa: PLR2004
    await workerA.complete_message(message=retriedMessage)
    await asyncio.sleep(1.5)
    assert await workerA.get_message() is None
