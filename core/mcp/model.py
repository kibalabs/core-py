import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import JsonValue


class McpUser(BaseModel):
    userId: str
    userName: str


class McpClient(BaseModel):
    clientId: str
    clientName: str
    redirectUris: list[str]


class McpCachedClient(BaseModel):
    client: McpClient
    expiryDate: datetime.datetime


class McpAuthorizationRequest(BaseModel):
    clientId: str
    clientName: str
    redirectUri: str
    clientState: str | None
    codeChallenge: str


class McpProviderLogin(BaseModel):
    authorizeUrl: str
    stateNonce: str


class McpTokenPair(BaseModel):
    accessToken: str
    refreshToken: str
    expiresInSeconds: int


class McpRequest(BaseModel):
    jsonrpc: Literal['2.0']
    id: int | str | None = None
    method: str
    params: dict[str, JsonValue] = Field(default_factory=dict)


class McpToolCall(BaseModel):
    name: str
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class McpHttpResponse(BaseModel):
    statusCode: int
    body: JsonValue = None


class McpNoArguments(BaseModel):
    model_config = ConfigDict(extra='forbid')
