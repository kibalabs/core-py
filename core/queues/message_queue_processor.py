import abc
import asyncio
import contextlib
import signal
import sys
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


class MessageLeaseLostException(InternalServerErrorException):
    def __init__(self) -> None:
        super().__init__(message='MESSAGE_LEASE_LOST')


class MessageQueueProcessor[MessageType: Message]:
    def __init__(
        self,
        queue: MessageQueue[MessageType],
        messageProcessor: MessageProcessor,
        notificationClients: list[NotificationClient],
        requestIdHolder: RequestIdHolder | None = None,
        pollLogIntervalSeconds: float = 600,
        shouldNotifyRetriedFailures: bool = True,
        deleteExpiredMessagesIntervalSeconds: float = 600,
    ) -> None:
        self.queue = queue
        self.messageProcessor = messageProcessor
        self.notificationClients = notificationClients
        self.requestIdHolder = requestIdHolder
        self.pollLogIntervalSeconds = pollLogIntervalSeconds
        self.shouldNotifyRetriedFailures = shouldNotifyRetriedFailures
        self.deleteExpiredMessagesIntervalSeconds = deleteExpiredMessagesIntervalSeconds
        self._lastPollLogTime: float | None = None
        self._lastExpiredDeletionTime: float | None = None
        self._shutdownEvent = asyncio.Event()

    def request_shutdown(self) -> None:
        # NOTE(krishan711): stops claiming new messages; the message being processed finishes and claimed messages not yet started are released
        self._shutdownEvent.set()

    async def _handle_failure(self, message: MessageType, exception: Exception, requestId: str) -> int:
        logging.error('Caught exception whilst processing message:')
        logging.exception(exception)
        kibaException = KibaException.from_exception(exception=exception)
        isRetryScheduled = await self.queue.fail_message(message=message, errorMessage=kibaException.message)
        if isRetryScheduled and not self.shouldNotifyRetriedFailures:
            logging.info(msg=f'Skipping failure notification for message:{message.command} as another attempt is scheduled')
        else:
            for client in self.notificationClients:
                try:
                    await client.post(messageText=f'Error processing message: {message.command}\n```\n{requestId}\n{message.content}\n{kibaException.exceptionType}: {kibaException.message}```')
                except Exception as notificationException:  # noqa: BLE001
                    logging.error('Failed to send message failure notification:')
                    logging.exception(notificationException)
        return exception.statusCode if isinstance(exception, KibaException) else 500

    async def _keep_message_alive(self, message: MessageType, expectedProcessingSeconds: int, stopEvent: asyncio.Event) -> bool:
        while True:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stopEvent.wait(), timeout=expectedProcessingSeconds / 3)
            if stopEvent.is_set():
                return False
            try:
                isExtended = await self.queue.extend_message_lease(message=message, expectedProcessingSeconds=expectedProcessingSeconds)
            except Exception as exception:  # noqa: BLE001
                logging.error(f'Failed to extend message lease {message.command}:')
                logging.exception(exception)
                continue
            if not isExtended:
                logging.error(f'Lost message lease for {message.command}')
                return True

    async def _process_message(self, message: MessageType, expectedProcessingSeconds: int) -> None:
        requestId = message.requestId or str(uuid.uuid4()).replace('-', '')
        if self.requestIdHolder:
            self.requestIdHolder.set_value(value=requestId)
        query = urlparse.urlencode(message.content, doseq=True)
        logging.api(action='MESSAGE', path=message.command, pathPattern=message.command, query=query)
        startTime = time.time()
        statusCode = 200
        # NOTE(krishan711): the keep-alive is stopped and awaited (not cancelled) so an in-flight extend finishes before the message is completed, retried or failed.
        # A lost lease is raised once the job returns rather than interrupting it, as cancelling mid-job could abandon work that was already sent.
        # It is raised from the finally so it replaces any exception from the job: the message belongs to another worker, so it must not be retried or completed here.
        # Cancellation (and other non-Exception errors) must still propagate, so those are never replaced.
        stopKeepAliveEvent = asyncio.Event()
        keepAliveTask = asyncio.create_task(self._keep_message_alive(message=message, expectedProcessingSeconds=expectedProcessingSeconds, stopEvent=stopKeepAliveEvent))
        isLeaseLost = False
        try:
            try:
                await self.messageProcessor.process_message(message=message)
            finally:
                stopKeepAliveEvent.set()
                isLeaseLost = await keepAliveTask
                inFlightException = sys.exception()
                if isLeaseLost and (inFlightException is None or isinstance(inFlightException, Exception)):
                    raise MessageLeaseLostException
            await self.queue.complete_message(message=message)
        except asyncio.CancelledError:
            if not isLeaseLost:
                await self._release_messages(messages=[message])
            raise
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

    async def _release_messages(self, messages: list[MessageType]) -> None:
        for message in messages:
            try:
                await self.queue.release_message(message=message)
            except Exception as exception:  # noqa: BLE001
                # NOTE(krishan711): a message that cannot be released is picked up again once its lease expires
                logging.error(f'Failed to release message {message.command}:')
                logging.exception(exception)

    async def _delete_expired_messages_if_due(self) -> None:
        now = time.monotonic()
        if self._lastExpiredDeletionTime is not None and now - self._lastExpiredDeletionTime < self.deleteExpiredMessagesIntervalSeconds:
            return
        self._lastExpiredDeletionTime = now
        try:
            deletedCount = await self.queue.delete_expired_messages()
        except Exception as exception:  # noqa: BLE001
            logging.error('Failed to delete expired messages:')
            logging.exception(exception)
            return
        if deletedCount > 0:
            logging.info(f'Deleted {deletedCount} expired messages')

    async def execute_batch(self, batchSize: int, expectedProcessingSeconds: int = 300, longPollSeconds: int = 20, shouldProcessInParallel: bool = False) -> int:
        now = time.monotonic()
        if self._lastPollLogTime is None or now - self._lastPollLogTime >= self.pollLogIntervalSeconds:
            logging.info('Retrieving messages...')
            self._lastPollLogTime = now
        messages = await self.queue.get_messages(expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds, limit=batchSize)
        if self._shutdownEvent.is_set():
            await self._release_messages(messages=messages)
        elif shouldProcessInParallel:
            await asyncio.gather(*[self._process_message(message=message, expectedProcessingSeconds=expectedProcessingSeconds) for message in messages])
        else:
            for index, message in enumerate(messages):
                if self._shutdownEvent.is_set():
                    await self._release_messages(messages=messages[index:])
                    break
                await self._process_message(message=message, expectedProcessingSeconds=expectedProcessingSeconds)
        return len(messages)

    async def execute(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 20) -> bool:
        processedMessageCount = await self.execute_batch(batchSize=1, expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds)
        return processedMessageCount > 0

    def _on_shutdown_signal(self, signalNumber: int) -> None:
        logging.info(f'Received {signal.Signals(signalNumber).name}, finishing the current message before shutting down')
        self.request_shutdown()
        # NOTE(krishan711): a second signal falls back to the default handler so an impatient interrupt still stops the process
        loop = asyncio.get_running_loop()
        for shutdownSignal in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(shutdownSignal)

    async def run_batches(
        self,
        batchSize: int,
        expectedProcessingSeconds: int = 300,
        longPollSeconds: int = 20,
        sleepTime: int = 30,
        totalMessageLimit: int | None = None,
        shouldProcessInParallel: bool = False,
    ) -> int:
        loop = asyncio.get_running_loop()
        for shutdownSignal in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(shutdownSignal, self._on_shutdown_signal, shutdownSignal)
        processedMessageCount = 0
        try:
            while not self._shutdownEvent.is_set() and (totalMessageLimit is None or processedMessageCount < totalMessageLimit):
                await self._delete_expired_messages_if_due()
                innerProcessedMessageCount = await self.execute_batch(expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds, batchSize=batchSize, shouldProcessInParallel=shouldProcessInParallel)
                if innerProcessedMessageCount == 0:
                    logging.info('No message received.. sleeping')
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(self._shutdownEvent.wait(), timeout=sleepTime)
                processedMessageCount += innerProcessedMessageCount
        finally:
            for shutdownSignal in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(shutdownSignal)
        if self._shutdownEvent.is_set():
            logging.info('Shutdown requested, stopped processing messages')
        return processedMessageCount

    async def run(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 20, sleepTime: int = 30, totalMessageLimit: int | None = None) -> bool:
        processedMessageCount = await self.run_batches(batchSize=1, sleepTime=sleepTime, totalMessageLimit=totalMessageLimit, expectedProcessingSeconds=expectedProcessingSeconds, longPollSeconds=longPollSeconds)
        return processedMessageCount > 0
