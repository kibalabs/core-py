import datetime
from abc import ABC
from abc import abstractmethod


class McpOAuthStore(ABC):
    # NOTE(krishan711): must be atomic: only the first claim of an unexpired key returns True
    @abstractmethod
    async def claim(self, key: str, lifetime: datetime.timedelta) -> bool: ...

    @abstractmethod
    async def is_claimed(self, key: str) -> bool: ...
