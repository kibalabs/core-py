from __future__ import annotations

import asyncio
from collections.abc import Sequence

from azure.storage.queue import QueueMessage as RawAqsMessage
from azure.storage.queue.aio import QueueClient

from core.exceptions import InternalServerErrorException
from core.queues.message_queue import MessageQueue
from core.queues.model import Message
from core.util import list_util


class AqsMessage(Message):
    aqsId: str
    popReceipt: str | None

    @classmethod
    def from_aqs_message(cls, aqsMessage: RawAqsMessage) -> AqsMessage:
        message = Message.model_validate_json(aqsMessage.content)
        return cls(
            command=message.command,
            content=message.content,
            requestId=message.requestId,
            postCount=message.postCount,
            postDate=message.postDate,
            deduplicationId=message.deduplicationId,
            aqsId=aqsMessage.id,
            popReceipt=aqsMessage.pop_receipt,
        )


class AqsMessageQueue(MessageQueue[AqsMessage]):
    def __init__(self, storageAccountName: str, storageAccountKey: str, queueName: str) -> None:
        self._storageAccountName = storageAccountName
        self._storageAccountKey = storageAccountKey
        self.queueName = queueName
        self._aqsClient: QueueClient | None = None

    async def connect(self) -> None:
        self._aqsClient = QueueClient.from_connection_string(conn_str=f'DefaultEndpointsProtocol=https;AccountName={self._storageAccountName};AccountKey={self._storageAccountKey}', queue_name=self.queueName)
        if not self._aqsClient:
            raise InternalServerErrorException('Failed to connect to queue')
        await self._aqsClient.get_queue_properties()

    async def disconnect(self) -> None:
        if not self._aqsClient:
            return
        await self._aqsClient.close()
        self._aqsClient = None

    async def send_message(self, message: Message, delaySeconds: int = 0) -> None:
        if not self._aqsClient:
            raise InternalServerErrorException('You need to call .connect() before trying to send messages')
        message.prepare_for_send()
        await self._aqsClient.send_message(visibility_timeout=delaySeconds, content=message.model_dump_json())

    async def send_messages(self, messages: Sequence[Message], delaySeconds: int = 0) -> None:
        if not self._aqsClient:
            raise InternalServerErrorException('You need to call .connect() before trying to send messages')
        for messageChunk in list_util.generate_chunks(lst=messages, chunkSize=10):
            await asyncio.gather(*[self.send_message(message=message, delaySeconds=delaySeconds) for message in messageChunk])

    async def get_message(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> AqsMessage | None:
        if not self._aqsClient:
            raise InternalServerErrorException('You need to call .connect() before trying to send messages')
        message = await self._aqsClient.receive_message(visibility_timeout=expectedProcessingSeconds, timeout=longPollSeconds)
        aqsMessage = AqsMessage.from_aqs_message(aqsMessage=message) if message else None
        return aqsMessage

    async def get_messages(self, limit: int = 1, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> list[AqsMessage]:
        if not self._aqsClient:
            raise InternalServerErrorException('You need to call .connect() before trying to get messages')
        messagesIterator = self._aqsClient.receive_messages(messages_per_page=min(limit, 10), max_messages=limit, visibility_timeout=expectedProcessingSeconds, timeout=longPollSeconds)
        aqsMessages = [AqsMessage.from_aqs_message(aqsMessage=message) async for message in messagesIterator]
        return aqsMessages

    async def complete_message(self, message: AqsMessage) -> None:
        if not self._aqsClient:
            raise InternalServerErrorException('You need to call .connect() before trying to complete messages')
        await self._aqsClient.delete_message(message=message.aqsId, pop_receipt=message.popReceipt)

    async def retry_message(self, message: AqsMessage, delaySeconds: int = 0) -> None:
        await self.send_message(message=message, delaySeconds=delaySeconds)
        await self.complete_message(message=message)

    async def fail_message(self, message: AqsMessage, errorMessage: str | None) -> None:
        # NOTE(krishan711): the message reappears after its visibility timeout
        pass

    async def extend_message_lease(self, message: AqsMessage, expectedProcessingSeconds: int) -> bool:
        if not self._aqsClient:
            raise InternalServerErrorException('You need to call .connect() before trying to extend message leases')
        updatedMessage = await self._aqsClient.update_message(message=message.aqsId, pop_receipt=message.popReceipt, visibility_timeout=expectedProcessingSeconds)
        # NOTE(krishan711): azure invalidates the old pop receipt on every update so later calls must use the new one
        message.popReceipt = updatedMessage.pop_receipt
        return True

    async def get_message_count(self) -> int:
        if not self._aqsClient:
            raise InternalServerErrorException('You need to call .connect() before trying to count messages')
        properties = await self._aqsClient.get_queue_properties()
        return int(properties.approximate_message_count or 0)

    async def get_inflight_message_count(self) -> int:
        raise NotImplementedError('Azure Storage Queues do not expose an in-flight message count')
