import abc
from abc import ABC
from typing import Generic
from typing import List
from typing import Optional
from typing import Sequence
from typing import TypeVar

from core.queues.model import Message

MessageType = TypeVar('MessageType', bound=Message)  # pylint: disable=invalid-name

class MessageQueue(Generic[MessageType], ABC):

    @abc.abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    async def disconnect(self) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    async def send_message(self, message: MessageType, delaySeconds: int = 0) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    async def send_messages(self, messages: Sequence[MessageType], delaySeconds: int = 0) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_message(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> Optional[MessageType]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_messages(self, limit: int = 1, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> List[MessageType]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def delete_message(self, message: MessageType) -> None:
        raise NotImplementedError()
