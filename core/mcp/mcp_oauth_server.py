from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import ipaddress
import re
import secrets
import typing
import urllib.parse
import uuid

from core import logging
from core.exceptions import BadRequestException
from core.exceptions import KibaException
from core.exceptions import UnauthorizedException
from core.http.jwt import KibaJwt
from core.mcp.mcp_identity_provider import McpIdentityProvider
from core.mcp.model import McpAuthorizationRequest
from core.mcp.model import McpCachedClient
from core.mcp.model import McpClient
from core.mcp.model import McpProviderLogin
from core.mcp.model import McpTokenPair
from core.mcp.model import McpUser
from core.mcp.oauth_store.mcp_oauth_store import McpOAuthStore
from core.util import date_util
from core.util import json_util
from core.util.typing_util import JsonObject

if typing.TYPE_CHECKING:
    from core.requester import Requester

JWT_KEY_ID = 'mcp-oauth-v1'
TOKEN_TYPE_KEY = 'tty'
AUDIENCE_KEY = 'aud'
CLIENT_ID_KEY = 'cid'
CLIENT_NAME_KEY = 'cnm'
CLIENT_REDIRECT_URIS_KEY = 'crs'
CLIENT_REDIRECT_URI_KEY = 'cru'
CLIENT_STATE_KEY = 'cst'
CODE_CHALLENGE_KEY = 'cch'
STATE_NONCE_KEY = 'non'
GRANT_ID_KEY = 'gid'
GRANT_EXPIRY_KEY = 'gex'
CONSENTS_KEY = 'cns'
CLIENT_REGISTRATION_LIFETIME = datetime.timedelta(days=365 * 100)
CONSENT_REQUEST_LIFETIME = datetime.timedelta(minutes=10)
MAX_CONSENT_COUNT = 20
CLIENT_METADATA_CACHE_LIFETIME = datetime.timedelta(hours=1)
MAX_CACHED_CLIENT_COUNT = 1000
PKCE_VERIFIER_PATTERN = re.compile(r'^[A-Za-z0-9\-._~]{43,128}$')
PKCE_S256_CHALLENGE_PATTERN = re.compile(r'^[A-Za-z0-9\-_]{43}$')
LOOPBACK_HOSTS = {'localhost', '127.0.0.1', '::1'}


# NOTE(krishan711): an OAuth 2.1 authorization server for MCP clients that delegates login to an identity provider. Tokens are
# typed signed JWTs; the store only records what must be single-use (state, codes, refresh tokens) or revoked.
class McpOAuthServer:
    def __init__(
        self,
        identityProvider: McpIdentityProvider,
        store: McpOAuthStore,
        jwtSecret: str,
        baseUrl: str,
        allowedRedirectUris: list[str] | None = None,
        requester: Requester | None = None,
        mcpPath: str = '/mcp',
        stateTokenLifetime: datetime.timedelta = datetime.timedelta(minutes=10),
        codeTokenLifetime: datetime.timedelta = datetime.timedelta(minutes=2),
        accessTokenLifetime: datetime.timedelta = datetime.timedelta(hours=1),
        refreshTokenLifetime: datetime.timedelta = datetime.timedelta(days=14),
        grantLifetime: datetime.timedelta = datetime.timedelta(days=30),
        consentLifetime: datetime.timedelta = datetime.timedelta(days=30),
    ) -> None:
        self.identityProvider = identityProvider
        self.store = store
        self._jwtSecret = jwtSecret.encode('utf-8')
        self.baseUrl = baseUrl.rstrip('/')
        self.allowedRedirectUris = set(allowedRedirectUris) if allowedRedirectUris is not None else None
        # NOTE(krishan711): enables Client ID Metadata Documents; pass a Requester that doesn't follow redirects (SSRF)
        self.requester = requester
        self.mcpPath = mcpPath
        self.resourceUrl = f'{self.baseUrl}{mcpPath}'
        self.providerCallbackUrl = f'{self.baseUrl}{mcpPath}/oauth/callback'
        self.stateTokenLifetime = stateTokenLifetime
        self.codeTokenLifetime = codeTokenLifetime
        self.accessTokenLifetime = accessTokenLifetime
        self.refreshTokenLifetime = refreshTokenLifetime
        self.grantLifetime = grantLifetime
        self.consentLifetime = consentLifetime
        self._cachedClients: dict[str, McpCachedClient] = {}

    def get_protected_resource_metadata(self, resourceName: str) -> JsonObject:
        return {'resource': self.resourceUrl, 'authorization_servers': [self.baseUrl], 'bearer_methods_supported': ['header'], 'resource_name': resourceName}

    def get_authorization_server_metadata(self) -> JsonObject:
        return {
            'issuer': self.baseUrl,
            'authorization_endpoint': f'{self.resourceUrl}/oauth/authorize',
            'token_endpoint': f'{self.resourceUrl}/oauth/token',
            'registration_endpoint': f'{self.resourceUrl}/oauth/register',
            'revocation_endpoint': f'{self.resourceUrl}/oauth/revoke',
            'response_types_supported': ['code'],
            'grant_types_supported': ['authorization_code', 'refresh_token'],
            'code_challenge_methods_supported': ['S256'],
            'token_endpoint_auth_methods_supported': ['none'],
            'revocation_endpoint_auth_methods_supported': ['none'],
            'authorization_response_iss_parameter_supported': True,
            'client_id_metadata_document_supported': self.requester is not None,
        }

    def register_client(self, redirectUris: list[str], clientName: str | None) -> JsonObject:
        if not redirectUris:
            raise BadRequestException(message='INVALID_REDIRECT_URI')
        for redirectUri in redirectUris:
            self._ensure_allowed_redirect_uri(redirectUri=redirectUri)
        name = clientName or 'MCP client'
        clientId = self._create_token(tokenType='mcpClient', lifetime=CLIENT_REGISTRATION_LIFETIME, claims={CLIENT_NAME_KEY: name, CLIENT_REDIRECT_URIS_KEY: redirectUris})
        return {
            'client_id': clientId,
            'client_id_issued_at': int(date_util.datetime_from_now().timestamp()),
            'client_name': name,
            'redirect_uris': redirectUris,
            'token_endpoint_auth_method': 'none',
            'grant_types': ['authorization_code', 'refresh_token'],
            'response_types': ['code'],
        }

    async def create_authorization_request(
        self,
        clientId: str,
        redirectUri: str,
        responseType: str | None,
        clientState: str | None,
        codeChallenge: str,
        codeChallengeMethod: str | None,
        resource: str | None,
    ) -> McpAuthorizationRequest:
        client = await self._resolve_client(clientId=clientId)
        if redirectUri not in client.redirectUris:
            raise BadRequestException(message='INVALID_REDIRECT_URI')
        self._ensure_allowed_redirect_uri(redirectUri=redirectUri)
        if responseType != 'code':
            raise BadRequestException(message='UNSUPPORTED_RESPONSE_TYPE')
        if codeChallengeMethod != 'S256' or not PKCE_S256_CHALLENGE_PATTERN.match(codeChallenge):
            raise BadRequestException(message='INVALID_CODE_CHALLENGE')
        if not self._is_valid_resource(resource=resource):
            raise BadRequestException(message='INVALID_TARGET')
        return McpAuthorizationRequest(clientId=client.clientId, clientName=client.clientName, redirectUri=redirectUri, clientState=clientState, codeChallenge=codeChallenge)

    def has_consent(self, consentToken: str | None, request: McpAuthorizationRequest) -> bool:
        return self._consent_key(request=request) in self._get_consent_keys(consentToken=consentToken)

    def create_consent_request_token(self, request: McpAuthorizationRequest) -> str:
        return self._create_token(tokenType='mcpConsentRequest', lifetime=CONSENT_REQUEST_LIFETIME, claims=self._request_claims(request=request))

    def get_consent_request(self, consentRequestToken: str) -> McpAuthorizationRequest:
        try:
            requestJwt = self._validate_token(tokenString=consentRequestToken, tokenType='mcpConsentRequest')
        except UnauthorizedException as exception:
            raise BadRequestException(message='INVALID_CONSENT_REQUEST') from exception
        return self._request_from_jwt(jwt=requestJwt)

    def add_consent(self, consentToken: str | None, request: McpAuthorizationRequest) -> str:
        consentKey = self._consent_key(request=request)
        consentKeys = [*[key for key in self._get_consent_keys(consentToken=consentToken) if key != consentKey], consentKey][-MAX_CONSENT_COUNT:]
        return self._create_token(tokenType='mcpConsent', lifetime=self.consentLifetime, claims={CONSENTS_KEY: consentKeys})

    def start_provider_login(self, request: McpAuthorizationRequest) -> McpProviderLogin:
        stateNonce = secrets.token_urlsafe(32)
        stateToken = self._create_token(tokenType='mcpState', lifetime=self.stateTokenLifetime, claims={**self._request_claims(request=request), STATE_NONCE_KEY: stateNonce})
        return McpProviderLogin(authorizeUrl=self.identityProvider.create_authorize_url(redirectUri=self.providerCallbackUrl, state=stateToken), stateNonce=stateNonce)

    def create_client_error_redirect(self, request: McpAuthorizationRequest, error: str) -> str:
        return self._client_redirect_url(redirectUri=request.redirectUri, params={'error': error, 'state': request.clientState})

    async def complete_provider_login(self, providerCode: str | None, stateToken: str, stateNonce: str | None) -> str:
        try:
            stateJwt = self._validate_token(tokenString=stateToken, tokenType='mcpState')
        except UnauthorizedException as exception:
            raise BadRequestException(message='INVALID_STATE') from exception
        if not stateNonce or not hmac.compare_digest(stateNonce, typing.cast(str, stateJwt.payloadDict[STATE_NONCE_KEY])):
            raise BadRequestException(message='STATE_NOT_FROM_THIS_BROWSER')
        if not await self.store.claim(key=f'state:{stateJwt.tokenId}', lifetime=self.stateTokenLifetime):
            raise BadRequestException(message='STATE_ALREADY_USED')
        request = self._request_from_jwt(jwt=stateJwt)
        if not providerCode:
            return self.create_client_error_redirect(request=request, error='access_denied')
        try:
            user = await self.identityProvider.authenticate_code(code=providerCode, redirectUri=self.providerCallbackUrl)
        except KibaException as exception:
            logging.warning(f'MCP provider login failed: {exception.message}')
            return self.create_client_error_redirect(request=request, error='access_denied')
        code = self._create_token(tokenType='mcpCode', lifetime=self.codeTokenLifetime, claims={**self._user_claims(user=user), **self._request_claims(request=request)})
        return self._client_redirect_url(redirectUri=request.redirectUri, params={'code': code, 'state': request.clientState})

    async def exchange_authorization_code(self, code: str, codeVerifier: str, redirectUri: str, clientId: str, resource: str | None) -> McpTokenPair:
        codeJwt = self._validate_token(tokenString=code, tokenType='mcpCode')
        if clientId != codeJwt.payloadDict[CLIENT_ID_KEY] or redirectUri != codeJwt.payloadDict[CLIENT_REDIRECT_URI_KEY] or not PKCE_VERIFIER_PATTERN.match(codeVerifier):
            raise UnauthorizedException(message='INVALID_GRANT')
        codeChallenge = base64.urlsafe_b64encode(hashlib.sha256(codeVerifier.encode('ascii')).digest()).decode('ascii').rstrip('=')
        if not hmac.compare_digest(codeChallenge, typing.cast(str, codeJwt.payloadDict[CODE_CHALLENGE_KEY])):
            raise UnauthorizedException(message='INVALID_GRANT')
        if not self._is_valid_resource(resource=resource):
            raise UnauthorizedException(message='INVALID_TARGET')
        if not await self.store.claim(key=f'code:{codeJwt.tokenId}', lifetime=self.codeTokenLifetime):
            raise UnauthorizedException(message='CODE_ALREADY_USED')
        grantExpiryDate = date_util.datetime_from_now(seconds=self.grantLifetime.total_seconds())
        return self._create_token_pair(user=self._user_from_jwt(jwt=codeJwt), clientId=clientId, grantId=str(uuid.uuid4()), grantExpiryTimestamp=int(grantExpiryDate.timestamp()))

    async def refresh_tokens(self, refreshToken: str, clientId: str | None, resource: str | None) -> McpTokenPair:
        refreshJwt = self._validate_token(tokenString=refreshToken, tokenType='mcpRefresh')
        tokenClientId = typing.cast(str, refreshJwt.payloadDict[CLIENT_ID_KEY])
        grantId = typing.cast(str, refreshJwt.payloadDict[GRANT_ID_KEY])
        if clientId is not None and clientId != tokenClientId:
            raise UnauthorizedException(message='INVALID_GRANT')
        if not self._is_valid_resource(resource=resource):
            raise UnauthorizedException(message='INVALID_TARGET')
        if await self.store.is_claimed(key=f'revoked:{grantId}'):
            raise UnauthorizedException(message='TOKEN_REVOKED')
        user = self._user_from_jwt(jwt=refreshJwt)
        await self.identityProvider.ensure_user_allowed(user=user)
        if not await self.store.claim(key=f'refresh:{refreshJwt.tokenId}', lifetime=self.refreshTokenLifetime):
            # NOTE(krishan711): a refresh token used twice has leaked, so the whole grant is revoked
            await self.store.claim(key=f'revoked:{grantId}', lifetime=self.grantLifetime)
            raise UnauthorizedException(message='REFRESH_TOKEN_REUSED')
        return self._create_token_pair(user=user, clientId=tokenClientId, grantId=grantId, grantExpiryTimestamp=typing.cast(int, refreshJwt.payloadDict[GRANT_EXPIRY_KEY]))

    async def revoke_token(self, token: str) -> None:
        for tokenType in ('mcpRefresh', 'mcpAccess'):
            try:
                tokenJwt = self._validate_token(tokenString=token, tokenType=tokenType)
            except UnauthorizedException:
                continue
            await self.store.claim(key=f'revoked:{tokenJwt.payloadDict[GRANT_ID_KEY]}', lifetime=self.grantLifetime)
            return

    async def validate_access_token(self, accessToken: str) -> McpUser:
        accessJwt = self._validate_token(tokenString=accessToken, tokenType='mcpAccess')
        if accessJwt.payloadDict.get(AUDIENCE_KEY) != self.resourceUrl:
            raise UnauthorizedException(message='INVALID_AUDIENCE')
        if await self.store.is_claimed(key=f'revoked:{accessJwt.payloadDict[GRANT_ID_KEY]}'):
            raise UnauthorizedException(message='TOKEN_REVOKED')
        return self._user_from_jwt(jwt=accessJwt)

    def _ensure_allowed_redirect_uri(self, redirectUri: str) -> None:
        if self.allowedRedirectUris is not None:
            if redirectUri not in self.allowedRedirectUris:
                raise BadRequestException(message='INVALID_REDIRECT_URI')
            return
        parsedUri = urllib.parse.urlparse(redirectUri)
        isLoopback = parsedUri.scheme == 'http' and parsedUri.hostname in LOOPBACK_HOSTS
        if (parsedUri.scheme != 'https' and not isLoopback) or not parsedUri.netloc or parsedUri.fragment:
            raise BadRequestException(message='INVALID_REDIRECT_URI')

    def _is_valid_resource(self, resource: str | None) -> bool:
        return resource is None or resource.rstrip('/') == self.resourceUrl

    async def _resolve_client(self, clientId: str) -> McpClient:
        if clientId.startswith('https://'):
            return await self._fetch_client_metadata(clientId=clientId)
        try:
            clientJwt = self._validate_token(tokenString=clientId, tokenType='mcpClient')
        except UnauthorizedException as exception:
            raise BadRequestException(message='INVALID_CLIENT') from exception
        return McpClient(clientId=clientId, clientName=typing.cast(str, clientJwt.payloadDict[CLIENT_NAME_KEY]), redirectUris=typing.cast(list[str], clientJwt.payloadDict[CLIENT_REDIRECT_URIS_KEY]))

    async def _fetch_client_metadata(self, clientId: str) -> McpClient:
        now = date_util.datetime_from_now()
        cachedClient = self._cachedClients.get(clientId)
        if cachedClient and cachedClient.expiryDate > now:
            return cachedClient.client
        parsedClientId = urllib.parse.urlparse(clientId)
        hostname = parsedClientId.hostname
        # NOTE(krishan711): the client id is chosen by the caller; this blocks ip literals and loopback, not names resolving to private ips
        if self.requester is None or hostname is None or parsedClientId.path in ('', '/') or hostname in LOOPBACK_HOSTS or _is_ip_address(hostname=hostname):
            raise BadRequestException(message='INVALID_CLIENT')
        try:
            document = json_util.loads((await self.requester.get(url=clientId, timeout=5)).content)
        except Exception as exception:
            raise BadRequestException(message='INVALID_CLIENT_METADATA') from exception
        if not isinstance(document, dict) or document.get('client_id') != clientId:
            raise BadRequestException(message='INVALID_CLIENT_METADATA')
        clientName = document.get('client_name')
        redirectUris = document.get('redirect_uris')
        if not isinstance(redirectUris, list) or not all(isinstance(redirectUri, str) for redirectUri in redirectUris):
            raise BadRequestException(message='INVALID_CLIENT_METADATA')
        client = McpClient(clientId=clientId, clientName=clientName if isinstance(clientName, str) else hostname, redirectUris=[str(redirectUri) for redirectUri in redirectUris])
        self._cachedClients = {key: value for key, value in self._cachedClients.items() if value.expiryDate > now}
        if len(self._cachedClients) < MAX_CACHED_CLIENT_COUNT:
            self._cachedClients[clientId] = McpCachedClient(client=client, expiryDate=now + CLIENT_METADATA_CACHE_LIFETIME)
        return client

    def _get_consent_keys(self, consentToken: str | None) -> list[str]:
        if not consentToken:
            return []
        try:
            consentJwt = self._validate_token(tokenString=consentToken, tokenType='mcpConsent')
        except UnauthorizedException:
            return []
        return typing.cast(list[str], consentJwt.payloadDict.get(CONSENTS_KEY, []))

    @staticmethod
    def _consent_key(request: McpAuthorizationRequest) -> str:
        return hashlib.sha256(f'{request.clientId}\n{request.redirectUri}'.encode()).hexdigest()[:32]

    @staticmethod
    def _request_claims(request: McpAuthorizationRequest) -> JsonObject:
        return {CLIENT_ID_KEY: request.clientId, CLIENT_NAME_KEY: request.clientName, CLIENT_REDIRECT_URI_KEY: request.redirectUri, CLIENT_STATE_KEY: request.clientState, CODE_CHALLENGE_KEY: request.codeChallenge}

    @staticmethod
    def _request_from_jwt(jwt: KibaJwt) -> McpAuthorizationRequest:
        return McpAuthorizationRequest(
            clientId=typing.cast(str, jwt.payloadDict[CLIENT_ID_KEY]),
            clientName=typing.cast(str, jwt.payloadDict[CLIENT_NAME_KEY]),
            redirectUri=typing.cast(str, jwt.payloadDict[CLIENT_REDIRECT_URI_KEY]),
            clientState=typing.cast(str | None, jwt.payloadDict.get(CLIENT_STATE_KEY)),
            codeChallenge=typing.cast(str, jwt.payloadDict[CODE_CHALLENGE_KEY]),
        )

    def _client_redirect_url(self, redirectUri: str, params: dict[str, str | None]) -> str:
        queryString = urllib.parse.urlencode({key: value for key, value in {**params, 'iss': self.baseUrl}.items() if value is not None})
        separator = '&' if '?' in redirectUri else '?'
        return f'{redirectUri}{separator}{queryString}'

    def _create_token_pair(self, user: McpUser, clientId: str, grantId: str, grantExpiryTimestamp: int) -> McpTokenPair:
        grantClaims: JsonObject = {**self._user_claims(user=user), CLIENT_ID_KEY: clientId, GRANT_ID_KEY: grantId, GRANT_EXPIRY_KEY: grantExpiryTimestamp}
        refreshLifetime = min(self.refreshTokenLifetime, datetime.datetime.fromtimestamp(grantExpiryTimestamp, tz=datetime.UTC) - date_util.datetime_from_now())
        if refreshLifetime <= datetime.timedelta(0):
            raise UnauthorizedException(message='GRANT_EXPIRED')
        accessToken = self._create_token(tokenType='mcpAccess', lifetime=min(self.accessTokenLifetime, refreshLifetime), claims={**grantClaims, AUDIENCE_KEY: self.resourceUrl})
        refreshToken = self._create_token(tokenType='mcpRefresh', lifetime=refreshLifetime, claims=grantClaims)
        return McpTokenPair(accessToken=accessToken, refreshToken=refreshToken, expiresInSeconds=int(min(self.accessTokenLifetime, refreshLifetime).total_seconds()))

    @staticmethod
    def _user_claims(user: McpUser) -> JsonObject:
        return {KibaJwt.Key.USER_ID: user.userId, KibaJwt.Key.USER_NAME: user.userName}

    @staticmethod
    def _user_from_jwt(jwt: KibaJwt) -> McpUser:
        return McpUser(userId=typing.cast(str, jwt.payloadDict[KibaJwt.Key.USER_ID]), userName=typing.cast(str, jwt.payloadDict[KibaJwt.Key.USER_NAME]))

    def _create_token(self, tokenType: str, lifetime: datetime.timedelta, claims: JsonObject) -> str:
        issueDate = date_util.datetime_from_now()
        jwt = KibaJwt(
            headerDict={KibaJwt.Key.ALGORITHM: 'HS256', KibaJwt.Key.TYPE: 'JWT', KibaJwt.Key.KEY_ID: JWT_KEY_ID},
            payloadDict={
                **claims,
                KibaJwt.Key.TOKEN_ID: str(uuid.uuid4()),
                TOKEN_TYPE_KEY: tokenType,
                KibaJwt.Key.ISSUE_DATE: int(issueDate.timestamp()),
                KibaJwt.Key.EXPIRY_DATE: int((issueDate + lifetime).timestamp()),
            },
        )
        jwt.signatureBytes = self._sign(jwt=jwt)
        return jwt.to_string()

    def _validate_token(self, tokenString: str, tokenType: str) -> KibaJwt:
        try:
            jwt = KibaJwt.from_string(jwtString=tokenString)
        except Exception as exception:
            raise UnauthorizedException(message='INVALID_TOKEN') from exception
        if not isinstance(jwt.headerDict, dict) or not isinstance(jwt.payloadDict, dict):
            raise UnauthorizedException(message='INVALID_TOKEN')
        if jwt.algorithm != 'HS256' or jwt.keyId != JWT_KEY_ID or not hmac.compare_digest(jwt.signatureBytes, self._sign(jwt=jwt)):
            raise UnauthorizedException(message='INVALID_TOKEN')
        if jwt.payloadDict.get(TOKEN_TYPE_KEY) != tokenType:
            raise UnauthorizedException(message='INVALID_TOKEN_TYPE')
        expiryDate = jwt.expiryDate
        if not expiryDate or expiryDate <= date_util.datetime_from_now():
            raise UnauthorizedException(message='TOKEN_EXPIRED')
        return jwt

    def _sign(self, jwt: KibaJwt) -> bytes:
        return hmac.new(self._jwtSecret, jwt.verificationString.encode('utf-8'), hashlib.sha256).digest()


def _is_ip_address(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return True
