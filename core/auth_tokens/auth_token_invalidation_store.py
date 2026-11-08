import datetime
from abc import ABC
from abc import abstractmethod


# NOTE(krishan711): records auth tokens (OAuth states, codes, refresh tokens, link secrets) and grants that must not be
# accepted again. Keep each invalidation until the token itself has expired; deleting one makes the token valid again
class AuthTokenInvalidationStore(ABC):
    # NOTE(krishan711): must be atomic: only the first invalidation of an unexpired key returns True
    @abstractmethod
    async def invalidate(self, key: str, lifetime: datetime.timedelta) -> bool: ...

    @abstractmethod
    async def is_invalidated(self, key: str) -> bool: ...
