from __future__ import annotations

from contextlib import AsyncExitStack
from typing import TYPE_CHECKING
from typing import Any
from typing import List
from typing import Optional
from typing import Sequence

from aiobotocore.session import get_session as get_botocore_session

from core.exceptions import InternalServerErrorException
from core.queues.message_queue import MessageQueue
from core.queues.model import Message
from core.util import list_util

if TYPE_CHECKING:
    from types_aiobotocore_sqs import SQSClient
    from types_aiobotocore_sqs.type_defs import MessageTypeDef as RawSqsMessageTypeDef
    from types_aiobotocore_sqs.type_defs import SendMessageBatchRequestEntryTypeDef
else:
    SQSClient = Any
    SendMessageBatchRequestEntryTypeDef = Any
    RawSqsMessageTypeDef = Any


class SqsMessage(Message):
    receiptHandle: str

    @classmethod
    def from_sqs_message(cls, sqsMessage: RawSqsMessageTypeDef) -> SqsMessage:
        message = Message.parse_raw(sqsMessage['Body'])
        return cls(
            command=message.command,
            content=message.content,
            requestId=message.requestId,
            postCount=message.postCount,
            postDate=message.postDate,
            receiptHandle=sqsMessage['ReceiptHandle'],
        )


class SqsMessageQueue(MessageQueue[SqsMessage]):

    def __init__(self, region: str, accessKeyId: str, accessKeySecret: str, queueUrl: str) -> None:
        self.region = region
        self._accessKeyId = accessKeyId
        self._accessKeySecret = accessKeySecret
        self.queueUrl = queueUrl
        self._exitStack = AsyncExitStack()
        self._sqsClient: Optional[SQSClient] = None

    async def connect(self) -> None:
        session = get_botocore_session()
        self._sqsClient = await self._exitStack.enter_async_context(session.create_client('sqs', region_name=self.region, aws_access_key_id=self._accessKeyId, aws_secret_access_key=self._accessKeySecret))

    async def disconnect(self) -> None:
        await self._exitStack.aclose()
        self._sqsClient = None

    async def send_message(self, message: Message, delaySeconds: int = 0) -> None:
        if not self._sqsClient:
            raise InternalServerErrorException("You need to call .connect() before trying to send messages")
        message.prepare_for_send()
        await self._sqsClient.send_message(QueueUrl=self.queueUrl, DelaySeconds=delaySeconds, MessageAttributes={}, MessageBody=message.json())

    async def send_messages(self, messages: Sequence[Message], delaySeconds: int = 0) -> None:
        if not self._sqsClient:
            raise InternalServerErrorException("You need to call .connect() before trying to send messages")
        failures = []
        for messageChunk in list_util.generate_chunks(lst=messages, chunkSize=10):
            requests: List[SendMessageBatchRequestEntryTypeDef] = []
            for index, message in enumerate(messageChunk):
                message.prepare_for_send()
                requests.append({'Id': str(index), 'DelaySeconds': int(delaySeconds), 'MessageAttributes': {}, 'MessageBody': message.json()})
            response = await self._sqsClient.send_message_batch(QueueUrl=self.queueUrl, Entries=requests)
            failures += response.get('Failed', [])
        if len(failures) > 0:
            errorMessage = ''
            for failure in failures:
                failureType = 'Sender' if failure['SenderFault'] else 'Receiver'
                errorMessage += f'{failureType} fault: id {failure["Id"]}, code {failure["Code"]}, message {failure.get("Message")}\n'
            raise InternalServerErrorException(message=errorMessage)

    async def get_message(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> Optional[SqsMessage]:
        messages = await self.get_messages(limit=1, expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds)
        return messages[0] if messages else None

    async def get_messages(self, limit: int = 1, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> List[SqsMessage]:
        if not self._sqsClient:
            raise InternalServerErrorException("You need to call .connect() before trying to get messages")
        sqsResponse = await self._sqsClient.receive_message(QueueUrl=self.queueUrl, VisibilityTimeout=expectedProcessingSeconds, MaxNumberOfMessages=limit, WaitTimeSeconds=longPollSeconds)
        sqsMessages = [SqsMessage.from_sqs_message(sqsMessage=sqsMessage) for sqsMessage in sqsResponse.get('Messages', [])]
        return sqsMessages

    async def delete_message(self, message: SqsMessage) -> None:
        if not self._sqsClient:
            raise InternalServerErrorException("You need to call .connect() before trying to delete messages")
        await self._sqsClient.delete_message(QueueUrl=self.queueUrl, ReceiptHandle=message.receiptHandle)
