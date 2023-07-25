from __future__ import annotations

import asyncio
from typing import List
from typing import Optional
from typing import Sequence

from azure.storage.queue import QueueMessage as RawAqsMessage
from azure.storage.queue.aio import QueueClient

from core.exceptions import InternalServerErrorException
from core.queues.message_queue import MessageQueue
from core.queues.model import Message
from core.util import list_util


class AqsMessage(Message):
    aqsId: str
    popReceipt: str

    @classmethod
    def from_aqs_message(cls, aqsMessage: RawAqsMessage) -> AqsMessage:
        message = Message.parse_raw(aqsMessage.content)
        return cls(
            command=message.command,
            content=message.content,
            requestId=message.requestId,
            postCount=message.postCount,
            postDate=message.postDate,
            aqsId=aqsMessage.id,
            popReceipt=aqsMessage.pop_receipt,
        )

class AqsMessageQueue(MessageQueue[AqsMessage]):

    def __init__(self, storageAccountName: str, storageAccountKey: str, queueName: str) -> None:
        self._storageAccountName = storageAccountName
        self._storageAccountKey = storageAccountKey
        self.queueName = queueName
        self._aqsClient: Optional[QueueClient] = None

    async def connect(self) -> None:
        self._aqsClient = QueueClient.from_connection_string(conn_str=f'DefaultEndpointsProtocol=https;AccountName={self._storageAccountName};AccountKey={self._storageAccountKey}', queue_name=self.queueName)
        if not self._aqsClient:
            raise InternalServerErrorException("Failed to connect to queue")
        await self._aqsClient.get_queue_properties()

    async def disconnect(self) -> None:
        if not self._aqsClient:
            return
        await self._aqsClient.close()  # type: ignore[no-untyped-call]
        self._aqsClient = None

    async def send_message(self, message: Message, delaySeconds: int = 0) -> None:
        if not self._aqsClient:
            raise InternalServerErrorException("You need to call .connect() before trying to send messages")
        message.prepare_for_send()
        await self._aqsClient.send_message(visibility_timeout=delaySeconds, content=message.json())

    async def send_messages(self, messages: Sequence[Message], delaySeconds: int = 0) -> None:
        if not self._aqsClient:
            raise InternalServerErrorException("You need to call .connect() before trying to send messages")
        for messageChunk in list_util.generate_chunks(lst=messages, chunkSize=10):
            await asyncio.gather(*[self.send_message(message=message, delaySeconds=delaySeconds) for message in messageChunk])

    async def get_message(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> Optional[AqsMessage]:
        if not self._aqsClient:
            raise InternalServerErrorException("You need to call .connect() before trying to send messages")
        message = await self._aqsClient.receive_message(visibility_timeout=expectedProcessingSeconds, timeout=longPollSeconds)
        aqsMessage = AqsMessage.from_aqs_message(aqsMessage=message)
        return aqsMessage

    async def get_messages(self, limit: int = 1, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> List[AqsMessage]:
        if not self._aqsClient:
            raise InternalServerErrorException("You need to call .connect() before trying to get messages")
        messagesIterator = self._aqsClient.receive_messages(messages_per_page=min(limit, 10), max_messages=limit, visibility_timeout=expectedProcessingSeconds, timeout=longPollSeconds)
        aqsMessages = [AqsMessage.from_aqs_message(aqsMessage=message) async for message in messagesIterator]
        return aqsMessages

    async def delete_message(self, message: AqsMessage) -> None:
        if not self._aqsClient:
            raise InternalServerErrorException("You need to call .connect() before trying to delete messages")
        await self._aqsClient.delete_message(message=message.aqsId, pop_receipt=message.popReceipt)
