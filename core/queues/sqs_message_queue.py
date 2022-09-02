from contextlib import AsyncExitStack
from typing import Optional
from typing import Sequence

from aiobotocore.session import get_session as get_botocore_session

from core.exceptions import InternalServerErrorException
from core.queues.model import Message
from core.queues.model import SqsMessage
from core.util import list_util


class SqsMessageQueue:

    def __init__(self, region: str, accessKeyId: str, accessKeySecret: str, queueUrl: str) -> None:
        self.region = region
        self._accessKeyId = accessKeyId
        self._accessKeySecret = accessKeySecret
        self.queueUrl = queueUrl
        self._exitStack = AsyncExitStack()
        self._sqsClient = None

    async def connect(self):
        session = get_botocore_session()
        self._sqsClient = await self._exitStack.enter_async_context(session.create_client('sqs', region_name=self.region, aws_access_key_id=self._accessKeyId, aws_secret_access_key=self._accessKeySecret))

    async def disconnect(self):
        await self._exitStack.aclose()
        self._sqsClient = None

    async def send_message(self, message: Message, delaySeconds: int = 0) -> None:
        message.prepare_for_send()
        await self._sqsClient.send_message(QueueUrl=self.queueUrl, DelaySeconds=delaySeconds, MessageAttributes={}, MessageBody=message.json())

    async def send_messages(self, messages: Sequence[Message], delaySeconds: int = 0) -> None:
        failures = []
        for messageChunk in list_util.generate_chunks(lst=messages, chunkSize=10):
            requests = []
            for index, message in enumerate(messageChunk):
                message.prepare_for_send()
                requests.append({'Id': str(index), 'DelaySeconds': delaySeconds, 'MessageAttributes': {}, 'MessageBody': message.json()})
            response = await self._sqsClient.send_message_batch(QueueUrl=self.queueUrl, Entries=requests)
            failures += response.get('Failed', [])
        if len(failures) > 0:
            message = ''
            for failure in failures:
                failureType = 'Sender' if failure['SenderFault'] else 'Receiver'
                message += f'{failureType} fault: id {failure["Id"]}, code {failure["Code"]}, message {failure.get("Message")}\n'
            raise InternalServerErrorException(message=message)

    async def get_message(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> Optional[SqsMessage]:
        messages = await self.get_messages(limit=1, expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds)
        return messages[0] if messages else None

    async def get_messages(self, limit: int = 1, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> Optional[Sequence[SqsMessage]]:
        sqsResponse = await self._sqsClient.receive_message(QueueUrl=self.queueUrl, VisibilityTimeout=expectedProcessingSeconds, MaxNumberOfMessages=limit, WaitTimeSeconds=longPollSeconds)
        sqsMessages = [SqsMessage.from_sqs_message(sqsMessage=sqsMessage) for sqsMessage in sqsResponse.get('Messages', [])]
        return sqsMessages

    async def delete_message(self, message: SqsMessage) -> None:
        await self._sqsClient.delete_message(QueueUrl=self.queueUrl, ReceiptHandle=message.receiptHandle)
