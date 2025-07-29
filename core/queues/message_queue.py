import abc
from abc import ABC
from collections.abc import Sequence

from core.queues.model import Message


class MessageQueue[MessageType: Message](ABC):
    @abc.abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def disconnect(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def send_message(self, message: MessageType, delaySeconds: int = 0) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def send_messages(self, messages: Sequence[MessageType], delaySeconds: int = 0) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_message(self, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> MessageType | None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_messages(self, limit: int = 1, expectedProcessingSeconds: int = 300, longPollSeconds: int = 0) -> list[MessageType]:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_message(self, message: MessageType) -> None:
        raise NotImplementedError
