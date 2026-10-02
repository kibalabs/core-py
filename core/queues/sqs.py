from __future__ import annotations

from collections.abc import Sequence
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING
from typing import Any

from aiobotocore.session import get_session as get_botocore_session
from botocore.exceptions import ClientError

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

SQS_MAX_DELAY_SECONDS = 900
SQS_LOST_LEASE_ERROR_CODES = {'ReceiptHandleIsInvalid', 'MessageNotInflight'}
SQS_MESSAGE_UNAVAILABLE_REASON = 'Message does not exist or is not available'
SQS_RETRY_HOLD_SECONDS = 60


class SqsMessage(Message):
    receiptHandle: str

    @classmethod
    def from_sqs_message(cls, sqsMessage: RawSqsMessageTypeDef) -> SqsMessage:
        message = Message.model_validate_json(sqsMessage['Body'])
        return cls(
            command=message.command,
            content=message.content,
            requestId=message.requestId,
            postCount=message.postCount,
            postDate=message.postDate,
            deduplicationId=message.deduplicationId,
            receiptHandle=sqsMessage['ReceiptHandle'],
        )


class SqsMessageQueue(MessageQueue[SqsMessage]):
    def __init__(self, region: str, accessKeyId: str, accessKeySecret: str, queueUrl: str, sessionToken: str | None = None, endpointUrl: str | None = None) -> None:
        self.region = region
        self._accessKeyId = accessKeyId
        self._accessKeySecret = accessKeySecret
        self._sessionToken = sessionToken
        self.queueUrl = queueUrl
        self.endpointUrl = endpointUrl
        self._exitStack = AsyncExitStack()
        self._sqsClient: SQSClient | None = None

    async def connect(self) -> None:
        session = get_botocore_session()
        self._sqsClient = await self._exitStack.enter_async_context(
            session.create_client('sqs', region_name=self.region, aws_access_key_id=self._accessKeyId, aws_secret_access_key=self._accessKeySecret, aws_session_token=self._sessionToken, endpoint_url=self.endpointUrl)
        )

    async def disconnect(self) -> None:
        await self._exitStack.aclose()
        self._sqsClient = None

    async def send_message(self, message: Message, delaySeconds: int = 0) -> None:
        if not self._sqsClient:
            raise InternalServerErrorException('You need to call .connect() before trying to send messages')
        message.prepare_for_send()
        await self._sqsClient.send_message(QueueUrl=self.queueUrl, DelaySeconds=min(delaySeconds, SQS_MAX_DELAY_SECONDS), MessageAttributes={}, MessageBody=message.model_dump_json())

    async def send_messages(self, messages: Sequence[Message], delaySeconds: int = 0) -> None:
        if not self._sqsClient:
            raise InternalServerErrorException('You need to call .connect() before trying to send messages')
        failures = []
        for messageChunk in list_util.generate_chunks(lst=messages, chunkSize=10):
            requests: list[SendMessageBatchRequestEntryTypeDef] = []
            for index, message in enumerate(messageChunk):
                message.prepare_for_send()
                requests.append({'Id': str(index), 'DelaySeconds': min(int(delaySeconds), SQS_MAX_DELAY_SECONDS), 'MessageAttributes': {}, 'MessageBody': message.model_dump_json()})
            response = await self._sqsClient.send_message_batch(QueueUrl=self.queueUrl, Entries=requests)
            failures += response.get('Failed', [])
        if len(failures) > 0:
            errorMessage = ''
            for failure in failures:
                failureType = 'Sender' if failure['SenderFault'] else 'Receiver'
                errorMessage += f'{failureType} fault: id {failure["Id"]}, code {failure["Code"]}, message {failure.get("Message")}\n'
            raise InternalServerErrorException(message=errorMessage)

    async def get_message(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> SqsMessage | None:
        messages = await self.get_messages(limit=1, expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds)
        return messages[0] if messages else None

    async def get_messages(self, limit: int = 1, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> list[SqsMessage]:
        if not self._sqsClient:
            raise InternalServerErrorException('You need to call .connect() before trying to get messages')
        sqsResponse = await self._sqsClient.receive_message(QueueUrl=self.queueUrl, VisibilityTimeout=expectedProcessingSeconds, MaxNumberOfMessages=limit, WaitTimeSeconds=longPollSeconds)
        sqsMessages = [SqsMessage.from_sqs_message(sqsMessage=sqsMessage) for sqsMessage in sqsResponse.get('Messages', [])]
        return sqsMessages

    async def complete_message(self, message: SqsMessage) -> None:
        if not self._sqsClient:
            raise InternalServerErrorException('You need to call .connect() before trying to complete messages')
        await self._sqsClient.delete_message(QueueUrl=self.queueUrl, ReceiptHandle=message.receiptHandle)

    async def retry_message(self, message: SqsMessage, delaySeconds: int = 0) -> None:
        # NOTE(krishan711): check the message is still in flight before re-sending so a message another worker already completed is not sent again
        if not await self.extend_message_lease(message=message, expectedProcessingSeconds=SQS_RETRY_HOLD_SECONDS):
            return
        await self.send_message(message=message, delaySeconds=delaySeconds)
        await self.complete_message(message=message)

    async def fail_message(self, message: SqsMessage, errorMessage: str | None) -> bool:  # noqa: ARG002
        # NOTE(krishan711): the message reappears after its visibility timeout and the queue's redrive policy decides when to dead-letter it
        return False

    async def extend_message_lease(self, message: SqsMessage, expectedProcessingSeconds: int) -> bool:
        if not self._sqsClient:
            raise InternalServerErrorException('You need to call .connect() before trying to extend message leases')
        try:
            await self._sqsClient.change_message_visibility(QueueUrl=self.queueUrl, ReceiptHandle=message.receiptHandle, VisibilityTimeout=expectedProcessingSeconds)
        except ClientError as exception:
            error = exception.response.get('Error', {})
            # NOTE(krishan711): real SQS accepts any receipt handle for a message (even one from an earlier receive), so a takeover by another worker cannot be
            # detected; only that the message has been deleted or is no longer in flight, which it reports as InvalidParameterValue with this reason
            if error.get('Code') in SQS_LOST_LEASE_ERROR_CODES or (error.get('Code') == 'InvalidParameterValue' and SQS_MESSAGE_UNAVAILABLE_REASON in error.get('Message', '')):
                return False
            raise
        return True

    async def get_message_count(self) -> int:
        if not self._sqsClient:
            raise InternalServerErrorException('You need to call .connect() before trying to count messages')
        response = await self._sqsClient.get_queue_attributes(QueueUrl=self.queueUrl, AttributeNames=['ApproximateNumberOfMessages'])
        return int(response['Attributes']['ApproximateNumberOfMessages'])

    async def get_inflight_message_count(self) -> int:
        if not self._sqsClient:
            raise InternalServerErrorException('You need to call .connect() before trying to count messages')
        response = await self._sqsClient.get_queue_attributes(QueueUrl=self.queueUrl, AttributeNames=['ApproximateNumberOfMessagesNotVisible'])
        return int(response['Attributes']['ApproximateNumberOfMessagesNotVisible'])
