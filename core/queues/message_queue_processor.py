import abc
import asyncio
import contextlib
import time
import urllib.parse as urlparse
import uuid
from abc import ABC

from core import logging
from core.exceptions import InternalServerErrorException
from core.exceptions import KibaException
from core.exceptions import LockedException
from core.notifications.notification_client import NotificationClient
from core.queues.message_queue import MessageQueue
from core.queues.model import Message
from core.util.value_holder import RequestIdHolder

LOCKED_MAX_RETRY_COUNT = 3
LOCKED_RETRY_DELAY_SECONDS = 30


class MessageProcessor(ABC):
    @abc.abstractmethod
    async def process_message(self, message: Message) -> None:
        pass


class MessageNeedsReprocessingException(InternalServerErrorException):
    def __init__(self, maxRetryCount: int = 3, delaySeconds: int = 60, originalException: KibaException | None = None) -> None:
        super().__init__(message='MessageNeedsReprocessingException')
        self.maxRetryCount = maxRetryCount
        self.delaySeconds = delaySeconds
        self.originalException = originalException


class MessageQueueProcessor[MessageType: Message]:
    def __init__(self, queue: MessageQueue[MessageType], messageProcessor: MessageProcessor, notificationClients: list[NotificationClient], requestIdHolder: RequestIdHolder | None = None) -> None:
        self.queue = queue
        self.messageProcessor = messageProcessor
        self.notificationClients = notificationClients
        self.requestIdHolder = requestIdHolder

    async def _handle_failure(self, message: MessageType, exception: Exception, requestId: str) -> int:
        logging.error('Caught exception whilst processing message:')
        logging.exception(exception)
        kibaException = KibaException.from_exception(exception=exception)
        await self.queue.fail_message(message=message, errorMessage=kibaException.message)
        for client in self.notificationClients:
            try:
                await client.post(messageText=f'Error processing message: {message.command}\n```\n{requestId}\n{message.content}\n{kibaException.message}```')
            except Exception as notificationException:  # noqa: BLE001
                logging.error('Failed to send message failure notification:')
                logging.exception(notificationException)
        return exception.statusCode if isinstance(exception, KibaException) else 500

    async def _keep_message_alive(self, message: MessageType, expectedProcessingSeconds: int, stopEvent: asyncio.Event) -> None:
        while True:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stopEvent.wait(), timeout=expectedProcessingSeconds / 3)
            if stopEvent.is_set():
                return
            try:
                isExtended = await self.queue.extend_message_lease(message=message, expectedProcessingSeconds=expectedProcessingSeconds)
            except Exception as exception:  # noqa: BLE001
                logging.error(f'Failed to extend message lease {message.command}:')
                logging.exception(exception)
                continue
            if not isExtended:
                logging.error(f'Lost message lease for {message.command}')
                return

    async def _process_message(self, message: MessageType, expectedProcessingSeconds: int) -> None:
        requestId = message.requestId or str(uuid.uuid4()).replace('-', '')
        if self.requestIdHolder:
            self.requestIdHolder.set_value(value=requestId)
        query = urlparse.urlencode(message.content, doseq=True)
        logging.api(action='MESSAGE', path=message.command, pathPattern=message.command, query=query)
        startTime = time.time()
        statusCode = 200
        # NOTE(krishan711): the keep-alive is stopped and awaited (not cancelled) so an in-flight extend finishes before the message is completed, retried or failed
        stopKeepAliveEvent = asyncio.Event()
        keepAliveTask = asyncio.create_task(self._keep_message_alive(message=message, expectedProcessingSeconds=expectedProcessingSeconds, stopEvent=stopKeepAliveEvent))
        try:
            try:
                await self.messageProcessor.process_message(message=message)
            finally:
                stopKeepAliveEvent.set()
                await keepAliveTask
            await self.queue.complete_message(message=message)
        except MessageNeedsReprocessingException as exception:
            logging.info(msg=f'Scheduling reprocessing for message:{message.command} due to: {exception.originalException!s}')
            await self.queue.retry_message(message=message, delaySeconds=((message.postCount or 0) * exception.delaySeconds))
        except LockedException as exception:
            postCount = message.postCount or 0
            if postCount <= LOCKED_MAX_RETRY_COUNT:
                logging.info(msg=f'Scheduling reprocessing for message:{message.command} due to: {exception!s}')
                await self.queue.retry_message(message=message, delaySeconds=(postCount * LOCKED_RETRY_DELAY_SECONDS))
            else:
                statusCode = await self._handle_failure(message=message, exception=exception, requestId=requestId)
        except Exception as exception:  # noqa: BLE001
            statusCode = await self._handle_failure(message=message, exception=exception, requestId=requestId)
        duration = time.time() - startTime
        logging.api(action='MESSAGE', path=message.command, pathPattern=message.command, query=query, response=statusCode, duration=duration)
        if self.requestIdHolder:
            self.requestIdHolder.set_value(value=None)

    async def execute_batch(self, batchSize: int, expectedProcessingSeconds: int = 300, longPollSeconds: int = 20, shouldProcessInParallel: bool = False) -> int:
        logging.info('Retrieving messages...')
        messages = await self.queue.get_messages(expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds, limit=batchSize)
        if shouldProcessInParallel:
            await asyncio.gather(*[self._process_message(message=message, expectedProcessingSeconds=expectedProcessingSeconds) for message in messages])
        else:
            for message in messages:
                await self._process_message(message=message, expectedProcessingSeconds=expectedProcessingSeconds)
        return len(messages)

    async def execute(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 20) -> bool:
        processedMessageCount = await self.execute_batch(batchSize=1, expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds)
        return processedMessageCount > 0

    async def run_batches(self, batchSize: int, expectedProcessingSeconds: int = 300, longPollSeconds: int = 20, sleepTime: int = 30, totalMessageLimit: int | None = None) -> int:
        processedMessageCount = 0
        while totalMessageLimit is None or processedMessageCount < totalMessageLimit:
            innerProcessedMessageCount = await self.execute_batch(expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds, batchSize=batchSize)
            if innerProcessedMessageCount == 0:
                logging.info('No message received.. sleeping')
                await asyncio.sleep(sleepTime)
            processedMessageCount += innerProcessedMessageCount
        return processedMessageCount

    async def run(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 20, sleepTime: int = 30, totalMessageLimit: int | None = None) -> bool:
        processedMessageCount = await self.run_batches(batchSize=1, sleepTime=sleepTime, totalMessageLimit=totalMessageLimit, expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds)
        return processedMessageCount > 0
