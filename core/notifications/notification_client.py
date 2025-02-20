import abc
from abc import ABC

from core.requester import KibaResponse


class NotificationClient(ABC):
    @abc.abstractmethod
    async def post(self, messageText: str) -> KibaResponse:
        pass
