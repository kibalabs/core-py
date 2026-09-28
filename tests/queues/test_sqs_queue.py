import asyncio
import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from aiobotocore.session import get_session

from core.queues.model import Message
from core.queues.sqs import SqsMessage
from core.queues.sqs import SqsMessageQueue

SQS_ENDPOINT = os.environ['CORE_TEST_SQS_ENDPOINT']

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def workers() -> AsyncIterator[tuple[SqsMessageQueue, SqsMessageQueue]]:
    async with get_session().create_client('sqs', region_name='us-east-1', aws_access_key_id='test', aws_secret_access_key='test', endpoint_url=SQS_ENDPOINT) as client:
        queueUrl = (await client.create_queue(QueueName=uuid.uuid4().hex))['QueueUrl']
    queues = [SqsMessageQueue(region='us-east-1', accessKeyId='test', accessKeySecret='test', queueUrl=queueUrl, endpointUrl=SQS_ENDPOINT) for _ in range(2)]
    for queue in queues:
        await queue.connect()
    yield queues[0], queues[1]
    for queue in queues:
        await queue.disconnect()


def _message() -> Message:
    return Message(command='DO_WORK', content={'userId': 'user-1'}, requestId=None, postCount=None, postDate=None, deduplicationId=None)


async def _claim(queue: SqsMessageQueue, expectedProcessingSeconds: int = 300) -> SqsMessage:
    message = await queue.get_message(expectedProcessingSeconds=expectedProcessingSeconds)
    assert message is not None
    return message


async def test_extended_message_stays_invisible_and_can_still_be_completed(workers: tuple[SqsMessageQueue, SqsMessageQueue]):
    workerA, workerB = workers
    await workerA.send_message(message=_message())
    message = await _claim(queue=workerA, expectedProcessingSeconds=1)
    assert await workerA.extend_message_lease(message=message, expectedProcessingSeconds=60) is True
    await asyncio.sleep(1.5)
    assert await workerB.get_message() is None
    await workerA.complete_message(message=message)
    assert await workerA.get_inflight_message_count() == 0


async def test_extend_after_another_worker_completed_the_message_reports_the_lease_lost(workers: tuple[SqsMessageQueue, SqsMessageQueue]):
    workerA, workerB = workers
    await workerA.send_message(message=_message())
    staleMessage = await _claim(queue=workerA, expectedProcessingSeconds=1)
    await asyncio.sleep(1.5)
    await workerB.complete_message(message=await _claim(queue=workerB))
    assert await workerA.extend_message_lease(message=staleMessage, expectedProcessingSeconds=60) is False


async def test_retry_after_another_worker_completed_the_message_does_not_send_it_again(workers: tuple[SqsMessageQueue, SqsMessageQueue]):
    workerA, workerB = workers
    await workerA.send_message(message=_message())
    staleMessage = await _claim(queue=workerA, expectedProcessingSeconds=1)
    await asyncio.sleep(1.5)
    await workerB.complete_message(message=await _claim(queue=workerB))
    await workerA.retry_message(message=staleMessage)
    assert await workerA.get_message() is None


async def test_retry_reschedules_without_leaving_the_original_behind(workers: tuple[SqsMessageQueue, SqsMessageQueue]):
    workerA, _ = workers
    await workerA.send_message(message=_message())
    await workerA.retry_message(message=await _claim(queue=workerA, expectedProcessingSeconds=1))
    retriedMessage = await _claim(queue=workerA)
    assert retriedMessage.postCount == 2  # noqa: PLR2004
    await workerA.complete_message(message=retriedMessage)
    await asyncio.sleep(1.5)
    assert await workerA.get_message() is None


async def test_delays_beyond_the_sqs_maximum_are_capped(workers: tuple[SqsMessageQueue, SqsMessageQueue]):
    workerA, _ = workers
    await workerA.send_message(message=_message(), delaySeconds=1800)
    await workerA.send_messages(messages=[_message()], delaySeconds=1800)
    assert await workerA.get_message() is None
