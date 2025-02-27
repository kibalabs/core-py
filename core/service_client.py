import os

from pydantic import BaseModel

from core.requester import Requester
from core.util import json_util


class ServiceClient:
    def __init__(self, requester: Requester, baseUrl: str) -> None:
        self.requester = requester
        self.baseUrl = baseUrl

    async def make_request(self, method: str, path: str, responseClass: type[BaseModel] | None = None, request: BaseModel | None = None) -> BaseModel | None:
        url = os.path.join(self.baseUrl, path)
        response = await self.requester.make_request(method=method, url=url, dataDict=request.model_dump() if request else None)
        return responseClass.model_validate(json_util.loads(response.content)) if responseClass else None
