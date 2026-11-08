from abc import ABC
from abc import abstractmethod

from core.mcp.model import McpUser


class McpIdentityProvider(ABC):
    @abstractmethod
    def create_authorize_url(self, redirectUri: str, state: str) -> str: ...

    @abstractmethod
    async def authenticate_code(self, code: str, redirectUri: str) -> McpUser: ...

    @abstractmethod
    async def ensure_user_allowed(self, user: McpUser) -> None: ...
