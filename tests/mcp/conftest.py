import base64
import hashlib
import urllib.parse
from types import SimpleNamespace

import pytest
from pydantic import BaseModel
from pydantic import ConfigDict
from starlette.applications import Starlette
from starlette.testclient import TestClient

from core.claims.dict_claim_store import DictClaimStore
from core.exceptions import BadRequestException
from core.exceptions import ForbiddenException
from core.mcp.mcp_identity_provider import McpIdentityProvider
from core.mcp.mcp_oauth_server import McpOAuthServer
from core.mcp.mcp_routes import create_mcp_routes
from core.mcp.mcp_server import McpServer
from core.mcp.model import McpNoArguments
from core.mcp.model import McpUser
from core.util import json_util

BASE_URL = 'https://api.example'
CLIENT_REDIRECT_URI = 'https://client.example/callback'
CIMD_CLIENT_ID = 'https://client.example/oauth/client.json'
CODE_VERIFIER = 'test-code-verifier-0123456789-0123456789-0123456789'
CODE_CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(CODE_VERIFIER.encode()).digest()).decode().rstrip('=')
CLIENT_CAPABILITIES = {'io.modelcontextprotocol/protocolVersion': '2026-07-28', 'io.modelcontextprotocol/clientCapabilities': {}}


class FakeIdentityProvider(McpIdentityProvider):
    def __init__(self) -> None:
        self.blockedUserIds: set[str] = set()

    def create_authorize_url(self, redirectUri: str, state: str) -> str:
        return f'https://login.example/authorize?{urllib.parse.urlencode({"redirect_uri": redirectUri, "state": state})}'

    async def authenticate_code(self, code: str, redirectUri: str) -> McpUser:
        if code == 'bad-code':
            raise ForbiddenException(message='INVALID_USER')
        return McpUser(userId=code, userName='Test User')

    async def ensure_user_allowed(self, user: McpUser) -> None:
        if user.userId in self.blockedUserIds:
            raise ForbiddenException(message='INVALID_USER')


class FakeRequester:
    def __init__(self) -> None:
        self.documents: dict[str, object] = {CIMD_CLIENT_ID: {'client_id': CIMD_CLIENT_ID, 'client_name': 'Metadata Client', 'redirect_uris': [CLIENT_REDIRECT_URI]}}
        self.requestedUrls: list[str] = []

    async def get(self, url: str, timeout: int | None = None):
        self.requestedUrls.append(url)
        if url not in self.documents:
            raise BadRequestException(message='not found')
        return SimpleNamespace(content=json_util.dumps(self.documents[url]).encode())


class EchoArguments(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str


class EchoResult(BaseModel):
    userId: str
    text: str


def create_oauth_server(identityProvider: McpIdentityProvider, requester: FakeRequester | None = None, secret: str = 'secret', allowedRedirectUris: list[str] | None = None) -> McpOAuthServer:
    return McpOAuthServer(identityProvider=identityProvider, store=DictClaimStore(), jwtSecret=secret, baseUrl=BASE_URL, allowedRedirectUris=allowedRedirectUris, requester=requester)


def create_mcp_server() -> McpServer:
    mcpServer = McpServer(name='test-server', version='1.0', instructions='Use the tools.', listTtlMs=60_000)

    async def echo(arguments: EchoArguments, user: McpUser) -> str:
        if arguments.text == 'fail':
            raise BadRequestException(message='echo failed')
        return f'{user.userId}: {arguments.text}'

    async def echo_structured(arguments: EchoArguments, user: McpUser) -> EchoResult:
        return EchoResult(userId=user.userId, text=arguments.text)

    async def whoami(arguments: McpNoArguments, user: McpUser) -> str:
        return user.userName

    mcpServer.register_tool(name='echo', title='Echo', description='Echo text', argumentsType=EchoArguments, handler=echo, isReadOnly=True)
    mcpServer.register_tool(name='echo_structured', title='Echo structured', description='Echo as data', argumentsType=EchoArguments, handler=echo_structured, outputType=EchoResult, isReadOnly=True)
    mcpServer.register_tool(name='whoami', title='Who am I', description='Current user', argumentsType=McpNoArguments, handler=whoami)
    return mcpServer


@pytest.fixture
def identityProvider() -> FakeIdentityProvider:
    return FakeIdentityProvider()


@pytest.fixture
def requester() -> FakeRequester:
    return FakeRequester()


@pytest.fixture
def oauthServer(identityProvider: FakeIdentityProvider, requester: FakeRequester) -> McpOAuthServer:
    return create_oauth_server(identityProvider=identityProvider, requester=requester)


@pytest.fixture
def client(oauthServer: McpOAuthServer) -> TestClient:
    app = Starlette(routes=create_mcp_routes(mcpServer=create_mcp_server(), oauthServer=oauthServer, resourceName='Test Data', maxBodyBytes=10_000))
    return TestClient(app, base_url=BASE_URL, follow_redirects=False)


def register(client: TestClient, redirectUris: list[str] | None = None) -> str:
    response = client.post('/mcp/oauth/register', json={'redirect_uris': redirectUris or [CLIENT_REDIRECT_URI], 'client_name': 'Test Client'})
    assert response.status_code == 201
    return response.json()['client_id']


def authorize_params(clientId: str, **overrides: str) -> dict[str, str]:
    return {'response_type': 'code', 'client_id': clientId, 'redirect_uri': CLIENT_REDIRECT_URI, 'code_challenge': CODE_CHALLENGE, 'code_challenge_method': 'S256', 'state': 'client-state', **overrides}


def query_params(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()}


def read_consent_form(client: TestClient, clientId: str) -> dict[str, str]:
    consentPage = client.get('/mcp/oauth/authorize', params=authorize_params(clientId=clientId))
    assert consentPage.status_code == 200
    return {name: consentPage.text.split(f'name="{name}" value="')[1].split('"')[0] for name in ('consent_request', 'csrf_token')}


def approve_consent(client: TestClient, clientId: str) -> str:
    authorizeResponse = client.get('/mcp/oauth/authorize', params=authorize_params(clientId=clientId))
    if authorizeResponse.status_code == 302:
        return authorizeResponse.headers['location']
    consentResponse = client.post('/mcp/oauth/consent', data={**read_consent_form(client=client, clientId=clientId), 'decision': 'approve'})
    assert consentResponse.status_code == 303
    return consentResponse.headers['location']


def create_code(client: TestClient, clientId: str, userId: str = 'user-1') -> str:
    providerUrl = approve_consent(client=client, clientId=clientId)
    callbackResponse = client.get('/mcp/oauth/callback', params={'code': userId, 'state': query_params(providerUrl)['state']})
    assert callbackResponse.status_code == 302
    return query_params(callbackResponse.headers['location'])['code']


def login(client: TestClient, userId: str = 'user-1') -> dict[str, str]:
    clientId = register(client=client)
    code = create_code(client=client, clientId=clientId, userId=userId)
    response = client.post('/mcp/oauth/token', data={'grant_type': 'authorization_code', 'code': code, 'code_verifier': CODE_VERIFIER, 'redirect_uri': CLIENT_REDIRECT_URI, 'client_id': clientId})
    assert response.status_code == 200
    return {**response.json(), 'client_id': clientId}
