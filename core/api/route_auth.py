from typing import Protocol

from pydantic import BaseModel

from core.api.api_request import KibaApiRequest


class RouteAuthResolver(Protocol):
    async def authorize_route[ApiRequest: BaseModel](self, *, auth: str, request: KibaApiRequest[ApiRequest]) -> None: ...

    def get_route_security_schemes(self, *, auth: str) -> list[str]: ...
