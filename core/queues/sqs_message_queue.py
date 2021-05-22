from typing import Optional
from typing import Sequence
from typing import TYPE_CHECKING

from core.queues.model import Message
from core.queues.model import SqsMessage

if TYPE_CHECKING:
    from mypy_boto3_sqs.client import SQSClient
else:
    SQSClient = None  # pylint: disable=invalid-name

class SqsMessageQueue:

    def __init__(self, sqsClient: SQSClient, queueUrl: str) -> None:
        self.sqsClient = sqsClient
        self.queueUrl = queueUrl

    async def send_message(self, message: Message, delaySeconds: int = 0) -> None:
        self.sqsClient.send_message(QueueUrl=self.queueUrl, DelaySeconds=delaySeconds, MessageAttributes={}, MessageBody=message.json())

    async def get_message(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> Optional[SqsMessage]:
        messages = await self.get_messages(limit=1, expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds)
        return messages[0] if messages else None

    async def get_messages(self, limit: int = 1, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> Optional[Sequence[SqsMessage]]:
        sqsResponse = self.sqsClient.receive_message(QueueUrl=self.queueUrl, VisibilityTimeout=expectedProcessingSeconds, MaxNumberOfMessages=limit, WaitTimeSeconds=longPollSeconds)
        sqsMessages = [SqsMessage.from_sqs_message(sqsMessage=sqsMessage) for sqsMessage in sqsResponse.get('Messages', [])]
        return sqsMessages

    async def delete_message(self, message: SqsMessage) -> None:
        self.sqsClient.delete_message(QueueUrl=self.queueUrl, ReceiptHandle=message.receiptHandle)
