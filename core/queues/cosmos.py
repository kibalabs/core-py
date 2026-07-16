from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from collections.abc import Sequence
from typing import Any

from azure.core import MatchConditions
from azure.cosmos import exceptions as cosmos_exceptions
from azure.cosmos.aio import ContainerProxy

from core.queues.message_queue import MessageQueue
from core.queues.model import Message
from core.util.typing_util import JsonObject


class CosmosMessage(Message):
    id: str
    leaseId: str
    etag: str

    @classmethod
    def from_item(cls, item: JsonObject) -> CosmosMessage:
        message = Message.model_validate(
            {
                'command': item['command'],
                'content': item['content'],
                'requestId': item.get('requestId'),
                'postCount': item.get('postCount'),
                'postDate': item.get('postDate'),
                'deduplicationId': item.get('deduplicationId'),
            }
        )
        return cls(
            command=message.command,
            content=message.content,
            requestId=message.requestId,
            postCount=message.postCount,
            postDate=message.postDate,
            deduplicationId=message.deduplicationId,
            id=str(item['id']),
            leaseId=str(item['leaseId']),
            etag=str(item['_etag']),
        )


class CosmosMessageQueue(MessageQueue[CosmosMessage]):
    def __init__(self, container: ContainerProxy, queueName: str, pollIntervalSeconds: float = 1.0) -> None:
        self.container = container
        self.queueName = queueName
        self.pollIntervalSeconds = pollIntervalSeconds

    async def connect(self) -> None:
        # The caller supplies a shared ContainerProxy and owns CosmosClient lifecycle.
        return None

    async def disconnect(self) -> None:
        # The caller supplies a shared ContainerProxy and owns CosmosClient lifecycle.
        return None

    @staticmethod
    def _item_body(message: Message, queueName: str, itemId: str, visibleDate: float, createdDate: float) -> dict[str, Any]:  # type: ignore[explicit-any]
        return {
            'id': itemId,
            'itemType': 'message',
            'queueName': queueName,
            'command': message.command,
            'content': message.content,
            'requestId': message.requestId,
            'postCount': message.postCount,
            'postDate': message.postDate.isoformat() if message.postDate else None,
            'deduplicationId': message.deduplicationId,
            'leaseId': None,
            'visibleDate': visibleDate,
            'createdDate': createdDate,
        }

    async def send_message(self, message: Message, delaySeconds: int = 0) -> None:
        await self.send_messages(messages=[message], delaySeconds=delaySeconds)

    async def send_messages(self, messages: Sequence[Message], delaySeconds: int = 0) -> None:
        if not messages:
            return
        now = time.time()
        visibleDate = now + delaySeconds
        for message in messages:
            message.prepare_for_send()
            itemId = uuid.uuid4().hex
            item = self._item_body(message=message, queueName=self.queueName, itemId=itemId, visibleDate=visibleDate, createdDate=now)
            if message.deduplicationId is None:
                # The SDK derives the create partition key from the body's queueName field.
                await self.container.create_item(body=item)
                continue

            deduplicationKey = f'{self.queueName}:{message.deduplicationId}'
            deduplicationItemId = f'dedup-{hashlib.sha256(deduplicationKey.encode()).hexdigest()}'
            deduplicationItem = {
                'id': deduplicationItemId,
                'itemType': 'deduplication',
                'queueName': self.queueName,
                'deduplicationId': message.deduplicationId,
                'messageId': itemId,
            }
            try:
                await self.container.execute_item_batch(
                    batch_operations=[
                        ('create', (deduplicationItem,)),
                        ('create', (item,)),
                    ],
                    partition_key=self.queueName,
                )
            except cosmos_exceptions.CosmosBatchOperationError as exception:
                if exception.error_index != 0 or exception.status_code != 409:  # noqa: PLR2004
                    raise

    async def get_message(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> CosmosMessage | None:
        messages = await self.get_messages(limit=1, expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds)
        return messages[0] if messages else None

    async def get_messages(self, limit: int = 1, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> list[CosmosMessage]:
        if limit <= 0:
            return []
        deadline = time.monotonic() + longPollSeconds
        while True:
            messages = await self._claim_messages(limit=limit, expectedProcessingSeconds=expectedProcessingSeconds)
            if messages or time.monotonic() >= deadline:
                return messages
            await asyncio.sleep(min(self.pollIntervalSeconds, max(deadline - time.monotonic(), 0)))

    async def _claim_messages(self, limit: int, expectedProcessingSeconds: int) -> list[CosmosMessage]:
        now = time.time()
        query = 'SELECT * FROM c WHERE c.itemType = @itemType AND c.queueName = @queueName AND c.visibleDate <= @now ORDER BY c.createdDate'
        candidates = self.container.query_items(
            query=query,
            parameters=[
                {'name': '@itemType', 'value': 'message'},
                {'name': '@queueName', 'value': self.queueName},
                {'name': '@now', 'value': now},
            ],
            partition_key=self.queueName,
            # Read ahead so ETag conflicts caused by concurrent workers do not unnecessarily
            # under-fill this batch; candidates that another worker claims are skipped.
            max_item_count=max(limit * 2, 10),
        )
        messages: list[CosmosMessage] = []
        async for candidate in candidates:
            item = {key: value for key, value in candidate.items() if not key.startswith('_')}
            leaseId = uuid.uuid4().hex
            item['leaseId'] = leaseId
            item['visibleDate'] = now + expectedProcessingSeconds
            try:
                claimedItem = await self.container.replace_item(
                    item=candidate['id'],
                    body=item,
                    etag=candidate['_etag'],
                    match_condition=MatchConditions.IfNotModified,
                    # The async SDK derives this from the body, but explicitly pass it in
                    # request options so the replace is targeted to this logical partition.
                    request_options={'partitionKey': self.queueName},
                )
            except cosmos_exceptions.CosmosHttpResponseError as exception:
                if exception.status_code == 412:  # noqa: PLR2004
                    continue
                raise
            messages.append(CosmosMessage.from_item(item=claimedItem))
            if len(messages) >= limit:
                break
        return messages

    async def delete_message(self, message: CosmosMessage) -> None:
        if message.deduplicationId is None:
            await self.container.delete_item(
                item=message.id,
                partition_key=self.queueName,
                etag=message.etag,
                match_condition=MatchConditions.IfNotModified,
            )
            return

        deduplicationKey = f'{self.queueName}:{message.deduplicationId}'
        deduplicationItemId = f'dedup-{hashlib.sha256(deduplicationKey.encode()).hexdigest()}'
        await self.container.execute_item_batch(
            batch_operations=[
                ('delete', (message.id,), {'if_match_etag': message.etag}),
                ('delete', (deduplicationItemId,)),
            ],
            partition_key=self.queueName,
        )
