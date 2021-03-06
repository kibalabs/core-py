import abc
import asyncio
import time
import urllib.parse as urlparse
import uuid
from abc import ABC
from typing import Optional

from core import logging
from core.exceptions import KibaException
from core.queues.model import Message
from core.queues.sqs_message_queue import SqsMessageQueue
from core.slack_client import SlackClient
from core.util.value_holder import RequestIdHolder


class MessageProcessor(ABC):

    @abc.abstractmethod
    async def process_message(self, message: Message) -> None:
        pass


class MessageQueueProcessor:

    def __init__(self, queue: SqsMessageQueue, messageProcessor: MessageProcessor, slackClient: Optional[SlackClient] = None, requestIdHolder: Optional[RequestIdHolder] = None):
        self.queue = queue
        self.messageProcessor = messageProcessor
        self.slackClient = slackClient
        self.requestIdHolder = requestIdHolder

    async def _process_message(self, message: Message) -> None:
        requestId = str(uuid.uuid4()).replace('-', '')
        if self.requestIdHolder:
            self.requestIdHolder.set_value(value=requestId)
        logging.api(action='MESSAGE', path=message.command, query=urlparse.urlencode(message.content, doseq=True))
        startTime = time.time()
        statusCode = 200
        try:
            await self.messageProcessor.process_message(message=message)
            await self.queue.delete_message(message=message)
        except Exception as exception:  # pylint: disable=broad-except
            statusCode = exception.statusCode if isinstance(exception, KibaException) else 500
            logging.error('Caught exception whilst processing message')
            logging.exception(exception)
            if self.slackClient:
                await self.slackClient.post(text=f'Error processing message: {message.command}\n```{requestId}\n{message.content}\n{exception}```')
            # TODO(krish): should possibly reset the visibility timeout
        duration = time.time() - startTime
        logging.api(action='MESSAGE', path=message.command, query=urlparse.urlencode(message.content, doseq=True), response=statusCode, duration=duration)
        if self.requestIdHolder:
            self.requestIdHolder.set_value(value=None)

    async def execute_batch(self, batchSize: int, expectedProcessingSeconds: int = 300, longPollSeconds: int = 20, shouldProcessInParallel: bool = False) -> int:
        logging.info('Retrieving messages...')
        messages = await self.queue.get_messages(expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds, limit=batchSize)
        if shouldProcessInParallel:
            await asyncio.gather(*[self._process_message(message=message) for message in messages])
        else:
            for message in messages:
                await self._process_message(message=message)
        return len(messages)

    async def execute(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 20) -> bool:
        processedMessageCount = await self.execute_batch(batchSize=1, expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds)
        return processedMessageCount > 0

    async def run_batches(self, batchSize: int, expectedProcessingSeconds: int = 300, longPollSeconds: int = 20, sleepTime: int = 30, totalMessageLimit: Optional[int] = None) -> int:
        processedMessageCount = 0
        while totalMessageLimit is None or processedMessageCount < totalMessageLimit:
            innerProcessedMessageCount = await self.execute_batch(expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds, batchSize=batchSize)
            if innerProcessedMessageCount == 0:
                logging.info('No message received.. sleeping')
                time.sleep(sleepTime)
            processedMessageCount += innerProcessedMessageCount
        return processedMessageCount

    async def run(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 20, sleepTime: int = 30, totalMessageLimit: Optional[int] = None) -> bool:
        processedMessageCount = await self.run_batches(batchSize=1, sleepTime=sleepTime, totalMessageLimit=totalMessageLimit, expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds)
        return processedMessageCount > totalMessageLimit
