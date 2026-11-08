import datetime

from core.mcp.oauth_store.mcp_oauth_store import McpOAuthStore


# NOTE(krishan711): only safe for a single process that is never restarted mid-flow; use SqlMcpOAuthStore otherwise
class DictMcpOAuthStore(McpOAuthStore):
    def __init__(self) -> None:
        self._expiryDates: dict[str, datetime.datetime] = {}

    async def claim(self, key: str, lifetime: datetime.timedelta) -> bool:
        self._remove_expired()
        if key in self._expiryDates:
            return False
        self._expiryDates[key] = datetime.datetime.now(tz=datetime.UTC) + lifetime
        return True

    async def is_claimed(self, key: str) -> bool:
        self._remove_expired()
        return key in self._expiryDates

    def _remove_expired(self) -> None:
        now = datetime.datetime.now(tz=datetime.UTC)
        for key in [key for key, expiryDate in self._expiryDates.items() if expiryDate <= now]:
            del self._expiryDates[key]
