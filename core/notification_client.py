import abc
from abc import ABC

class NotificationsClient(ABC):

    @abc.abstractmethod
    async def post(self, messageText: str) -> None:
        pass