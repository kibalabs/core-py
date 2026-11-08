import datetime
from abc import ABC
from abc import abstractmethod


# NOTE(krishan711): records auth tokens (OAuth states, codes, refresh tokens, link secrets) and revocations that must
# only be used once. Rows are kept until they expire, which should be no sooner than the token itself expires
class AuthUsedTokenStore(ABC):
    # NOTE(krishan711): must be atomic: only the first mark of an unexpired key returns True
    @abstractmethod
    async def mark_used(self, key: str, lifetime: datetime.timedelta) -> bool: ...

    @abstractmethod
    async def is_used(self, key: str) -> bool: ...
