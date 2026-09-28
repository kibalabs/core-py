import asyncio
import os
import time
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from azure.cosmos import PartitionKey
from azure.cosmos.aio import ContainerProxy
from azure.cosmos.aio import CosmosClient

from core.queues.cosmos import CosmosMessage
from core.queues.cosmos import CosmosMessageQueue
from core.queues.model import Message

COSMOS_ENDPOINT = os.environ['CORE_TEST_COSMOS_ENDPOINT']
# NOTE: the public, fixed key every cosmos emulator uses
COSMOS_EMULATOR_KEY = 'C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=='

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def container() -> AsyncIterator[ContainerProxy]:
    async with CosmosClient(url=COSMOS_ENDPOINT, credential=COSMOS_EMULATOR_KEY) as client:
        database = await client.create_database_if_not_exists(id='core-tests')
        yield await database.create_container_if_not_exists(id='queue', partition_key=PartitionKey(path='/queueName'))


@pytest_asyncio.fixture
async def workers(container: ContainerProxy) -> tuple[CosmosMessageQueue, CosmosMessageQueue]:
    # NOTE: a fresh queue name per test isolates tests inside the shared container
    queueName = uuid.uuid4().hex
    return CosmosMessageQueue(container=container, queueName=queueName, pollIntervalSeconds=0.05), CosmosMessageQueue(container=container, queueName=queueName, pollIntervalSeconds=0.05)


def _message(deduplicationId: str | None = 'dedup', userId: str = 'user-1') -> Message:
    return Message(command='DO_WORK', content={'userId': userId}, requestId=None, postCount=None, postDate=None, deduplicationId=deduplicationId)


async def _make_visible(queue: CosmosMessageQueue, messageId: str) -> None:
    await queue.container.patch_item(item=messageId, partition_key=queue.queueName, patch_operations=[{'op': 'set', 'path': '/visibleDate', 'value': time.time() - 1}])


async def _claim(queue: CosmosMessageQueue) -> CosmosMessage:
    message = await queue.get_message()
    assert message is not None
    return message


async def test_identical_messages_are_deduplicated(workers: tuple[CosmosMessageQueue, CosmosMessageQueue]):
    workerA, _ = workers
    await workerA.send_message(message=_message())
    await workerA.send_messages(messages=[_message(), _message()])
    assert await workerA.get_message_count() == 1


async def test_messages_without_deduplication_id_are_all_kept(workers: tuple[CosmosMessageQueue, CosmosMessageQueue]):
    workerA, _ = workers
    await workerA.send_messages(messages=[_message(deduplicationId=None), _message(deduplicationId=None)])
    assert await workerA.get_message_count() == 2  # noqa: PLR2004


async def test_delayed_message_is_not_claimed_until_visible(workers: tuple[CosmosMessageQueue, CosmosMessageQueue]):
    workerA, _ = workers
    await workerA.send_message(message=_message(), delaySeconds=60)
    assert await workerA.get_message() is None


async def test_concurrent_claims_never_hand_out_the_same_message(workers: tuple[CosmosMessageQueue, CosmosMessageQueue]):
    await workers[0].send_messages(messages=[_message(deduplicationId=None, userId=str(index)) for index in range(10)])
    results = await asyncio.gather(*[worker.get_messages(limit=2) for _ in range(5) for worker in workers])
    claimedIds = [message.id for messages in results for message in messages]
    assert len(claimedIds) == len(set(claimedIds)) == 10  # noqa: PLR2004


async def test_completed_message_is_removed_and_can_be_sent_again(workers: tuple[CosmosMessageQueue, CosmosMessageQueue]):
    workerA, _ = workers
    await workerA.send_message(message=_message())
    await workerA.complete_message(message=await _claim(queue=workerA))
    assert await workerA.get_message_count() == 0
    assert await workerA.get_inflight_message_count() == 0
    await workerA.send_message(message=_message())
    assert await workerA.get_message_count() == 1


async def test_retry_reschedules_the_same_message_with_a_delay(workers: tuple[CosmosMessageQueue, CosmosMessageQueue]):
    workerA, _ = workers
    await workerA.send_message(message=_message())
    message = await _claim(queue=workerA)
    await workerA.retry_message(message=message, delaySeconds=60)
    assert await workerA.get_message() is None
    await _make_visible(queue=workerA, messageId=message.id)
    retriedMessage = await _claim(queue=workerA)
    assert retriedMessage.id == message.id
    assert retriedMessage.postCount == 2  # noqa: PLR2004


async def test_retry_after_losing_the_lease_leaves_the_new_holder_untouched(workers: tuple[CosmosMessageQueue, CosmosMessageQueue]):
    workerA, workerB = workers
    await workerA.send_message(message=_message())
    staleMessage = await _claim(queue=workerA)
    await _make_visible(queue=workerA, messageId=staleMessage.id)
    newMessage = await _claim(queue=workerB)
    await workerA.retry_message(message=staleMessage)
    assert await workerA.get_inflight_message_count() == 1
    await workerB.complete_message(message=newMessage)
    assert await workerA.get_inflight_message_count() == 0


async def test_failed_message_reappears_once_its_lease_expires(workers: tuple[CosmosMessageQueue, CosmosMessageQueue]):
    workerA, _ = workers
    await workerA.send_message(message=_message())
    message = await _claim(queue=workerA)
    await workerA.fail_message(message=message, errorMessage='boom')
    assert await workerA.get_message() is None
    await _make_visible(queue=workerA, messageId=message.id)
    assert (await _claim(queue=workerA)).id == message.id
