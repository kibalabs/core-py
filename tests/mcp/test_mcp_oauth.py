import datetime

import pytest
from starlette.testclient import TestClient

from core.exceptions import BadRequestException
from core.exceptions import UnauthorizedException
from core.http.jwt import KibaJwt
from core.mcp.model import McpAuthorizationRequest
from core.mcp.model import McpUser
from tests.mcp.conftest import BASE_URL
from tests.mcp.conftest import CIMD_CLIENT_ID
from tests.mcp.conftest import CLIENT_REDIRECT_URI
from tests.mcp.conftest import CODE_VERIFIER
from tests.mcp.conftest import FakeIdentityProvider
from tests.mcp.conftest import FakeRequester
from tests.mcp.conftest import approve_consent
from tests.mcp.conftest import authorize_params
from tests.mcp.conftest import create_code
from tests.mcp.conftest import create_oauth_server
from tests.mcp.conftest import login
from tests.mcp.conftest import query_params
from tests.mcp.conftest import read_consent_form
from tests.mcp.conftest import register


def ping(client: TestClient, accessToken: str) -> int:
    return client.post('/mcp', headers={'Authorization': f'Bearer {accessToken}'}, json={'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}).status_code


def exchange_code(client: TestClient, code: str, clientId: str, codeVerifier: str = CODE_VERIFIER, redirectUri: str = CLIENT_REDIRECT_URI, **extra: str) -> dict[str, str]:
    return client.post('/mcp/oauth/token', data={'grant_type': 'authorization_code', 'code': code, 'code_verifier': codeVerifier, 'redirect_uri': redirectUri, 'client_id': clientId, **extra}).json()


def refresh(client: TestClient, refreshToken: str) -> dict[str, str]:
    return client.post('/mcp/oauth/token', data={'grant_type': 'refresh_token', 'refresh_token': refreshToken}).json()


def test_metadata_advertises_endpoints_and_features(client: TestClient) -> None:
    assert client.get('/.well-known/oauth-protected-resource/mcp').json()['resource'] == f'{BASE_URL}/mcp'
    metadata = client.get('/.well-known/oauth-authorization-server').json()
    assert metadata['revocation_endpoint'] == f'{BASE_URL}/mcp/oauth/revoke'
    assert metadata['authorization_response_iss_parameter_supported'] is True
    assert metadata['client_id_metadata_document_supported'] is True
    assert metadata['code_challenge_methods_supported'] == ['S256']


@pytest.mark.parametrize('redirectUri', ['http://client.example/callback', 'https://client.example/callback#fragment', 'not-a-url'])
def test_register_rejects_unsafe_redirect_uris(client: TestClient, redirectUri: str) -> None:
    response = client.post('/mcp/oauth/register', json={'redirect_uris': [redirectUri]})
    assert response.status_code == 400
    assert response.json()['error'] == 'invalid_redirect_uri'


@pytest.mark.parametrize('redirectUri', ['http://127.0.0.1:6274/callback', 'http://localhost/callback', 'http://[::1]:6274/callback'])
def test_register_accepts_loopback_http_redirect_uris(client: TestClient, redirectUri: str) -> None:
    assert client.post('/mcp/oauth/register', json={'redirect_uris': [redirectUri]}).status_code == 201


def test_register_enforces_the_redirect_allowlist_when_configured(identityProvider: FakeIdentityProvider) -> None:
    oauthServer = create_oauth_server(identityProvider=identityProvider, allowedRedirectUris=[CLIENT_REDIRECT_URI])
    oauthServer.register_client(redirectUris=[CLIENT_REDIRECT_URI], clientName=None)
    with pytest.raises(BadRequestException, match='INVALID_REDIRECT_URI'):
        oauthServer.register_client(redirectUris=['https://other.example/callback'], clientName=None)


@pytest.mark.parametrize(
    ('overrides', 'expectedMessage'),
    [
        ({'client_id': 'not-a-client'}, 'INVALID_CLIENT'),
        ({'redirect_uri': 'https://client.example/other'}, 'INVALID_REDIRECT_URI'),
        ({'response_type': 'token'}, 'UNSUPPORTED_RESPONSE_TYPE'),
        ({'code_challenge_method': 'plain'}, 'INVALID_CODE_CHALLENGE'),
        ({'code_challenge': 'too-short'}, 'INVALID_CODE_CHALLENGE'),
        ({'resource': 'https://other.example/mcp'}, 'INVALID_TARGET'),
    ],
)
def test_authorize_rejects_invalid_requests_without_redirecting(client: TestClient, overrides: dict[str, str], expectedMessage: str) -> None:
    clientId = register(client=client)
    response = client.get('/mcp/oauth/authorize', params=authorize_params(clientId=clientId, **overrides))
    assert response.status_code == 400
    assert expectedMessage in response.text


def test_authorize_shows_a_consent_page_that_cannot_be_framed(client: TestClient) -> None:
    clientId = register(client=client)
    response = client.get('/mcp/oauth/authorize', params=authorize_params(clientId=clientId))
    assert response.status_code == 200
    assert 'Test Client' in response.text
    assert 'client.example' in response.text
    assert "frame-ancestors 'none'" in response.headers['content-security-policy']
    assert 'form-action' not in response.headers['content-security-policy']
    assert response.headers['x-frame-options'] == 'DENY'
    assert '__Host-mcp-csrf=' in response.headers['set-cookie']


def test_consent_is_remembered_per_client(client: TestClient) -> None:
    clientId = register(client=client)
    approve_consent(client=client, clientId=clientId)
    sameClientResponse = client.get('/mcp/oauth/authorize', params=authorize_params(clientId=clientId))
    assert sameClientResponse.status_code == 302
    assert sameClientResponse.headers['location'].startswith('https://login.example/authorize')
    otherClientResponse = client.get('/mcp/oauth/authorize', params=authorize_params(clientId=register(client=client)))
    assert otherClientResponse.status_code == 200


def test_consent_rejects_a_post_without_the_csrf_cookie(client: TestClient) -> None:
    consentForm = read_consent_form(client=client, clientId=register(client=client))
    client.cookies.clear()
    assert client.post('/mcp/oauth/consent', data={**consentForm, 'decision': 'approve'}).status_code == 403


def test_denying_consent_redirects_with_access_denied(client: TestClient) -> None:
    consentForm = read_consent_form(client=client, clientId=register(client=client))
    response = client.post('/mcp/oauth/consent', data={**consentForm, 'decision': 'deny'})
    assert response.status_code == 303
    assert query_params(response.headers['location']) == {'error': 'access_denied', 'state': 'client-state', 'iss': BASE_URL}


def test_callback_returns_code_state_and_issuer(client: TestClient) -> None:
    clientId = register(client=client)
    providerUrl = approve_consent(client=client, clientId=clientId)
    response = client.get('/mcp/oauth/callback', params={'code': 'user-1', 'state': query_params(providerUrl)['state']})
    params = query_params(response.headers['location'])
    assert response.headers['location'].startswith(CLIENT_REDIRECT_URI)
    assert params['state'] == 'client-state'
    assert params['iss'] == BASE_URL
    assert 'code' in params


def test_callback_rejects_a_state_from_another_browser(client: TestClient) -> None:
    clientId = register(client=client)
    providerUrl = approve_consent(client=client, clientId=clientId)
    client.cookies.clear()
    response = client.get('/mcp/oauth/callback', params={'code': 'user-1', 'state': query_params(providerUrl)['state']})
    assert response.status_code == 400
    assert 'STATE_NOT_FROM_THIS_BROWSER' in response.text


def test_callback_state_is_single_use(client: TestClient) -> None:
    clientId = register(client=client)
    providerUrl = approve_consent(client=client, clientId=clientId)
    stateCookie = client.cookies.get('__Host-mcp-state')
    assert client.get('/mcp/oauth/callback', params={'code': 'user-1', 'state': query_params(providerUrl)['state']}).status_code == 302
    client.cookies.set('__Host-mcp-state', stateCookie)
    response = client.get('/mcp/oauth/callback', params={'code': 'user-1', 'state': query_params(providerUrl)['state']})
    assert response.status_code == 400
    assert 'STATE_ALREADY_USED' in response.text


def test_callback_sends_access_denied_when_the_provider_rejects_the_user(client: TestClient) -> None:
    clientId = register(client=client)
    providerUrl = approve_consent(client=client, clientId=clientId)
    response = client.get('/mcp/oauth/callback', params={'code': 'bad-code', 'state': query_params(providerUrl)['state']})
    assert query_params(response.headers['location']) == {'error': 'access_denied', 'state': 'client-state', 'iss': BASE_URL}


def test_tokens_work_and_codes_are_single_use(client: TestClient) -> None:
    clientId = register(client=client)
    code = create_code(client=client, clientId=clientId)
    tokens = exchange_code(client=client, code=code, clientId=clientId)
    assert ping(client=client, accessToken=tokens['access_token']) == 200
    assert exchange_code(client=client, code=code, clientId=clientId)['error'] == 'invalid_grant'


@pytest.mark.parametrize('codeVerifier', ['wrong-verifier-0123456789-0123456789-0123456789', 'short', 'ünicode-verifier-0123456789-0123456789-0123456789'])
def test_token_rejects_wrong_or_malformed_verifiers(client: TestClient, codeVerifier: str) -> None:
    clientId = register(client=client)
    code = create_code(client=client, clientId=clientId)
    assert exchange_code(client=client, code=code, clientId=clientId, codeVerifier=codeVerifier)['error'] == 'invalid_grant'


def test_token_rejects_another_client_redirect_or_resource(client: TestClient) -> None:
    clientId = register(client=client)
    assert exchange_code(client=client, code=create_code(client=client, clientId=clientId), clientId=register(client=client))['error'] == 'invalid_grant'
    assert exchange_code(client=client, code=create_code(client=client, clientId=clientId), clientId=clientId, redirectUri='https://client.example/other')['error'] == 'invalid_grant'
    assert exchange_code(client=client, code=create_code(client=client, clientId=clientId), clientId=clientId, resource='https://other.example/mcp')['error'] == 'invalid_target'


def test_refresh_rotates_and_reuse_revokes_the_grant(client: TestClient) -> None:
    tokens = login(client=client)
    refreshedTokens = refresh(client=client, refreshToken=tokens['refresh_token'])
    assert ping(client=client, accessToken=refreshedTokens['access_token']) == 200
    assert refresh(client=client, refreshToken=tokens['refresh_token'])['error'] == 'invalid_grant'
    assert ping(client=client, accessToken=refreshedTokens['access_token']) == 401
    assert refresh(client=client, refreshToken=refreshedTokens['refresh_token'])['error'] == 'invalid_grant'


def test_refresh_rechecks_the_user_with_the_identity_provider(client: TestClient, identityProvider: FakeIdentityProvider) -> None:
    tokens = login(client=client, userId='user-1')
    identityProvider.blockedUserIds.add('user-1')
    assert refresh(client=client, refreshToken=tokens['refresh_token'])['error'] == 'invalid_grant'
    identityProvider.blockedUserIds.clear()
    assert 'access_token' in refresh(client=client, refreshToken=tokens['refresh_token'])


def test_access_and_refresh_tokens_are_not_interchangeable(client: TestClient) -> None:
    tokens = login(client=client)
    assert ping(client=client, accessToken=tokens['refresh_token']) == 401
    assert refresh(client=client, refreshToken=tokens['access_token'])['error'] == 'invalid_grant'


@pytest.mark.parametrize('tokenName', ['access_token', 'refresh_token'])
def test_revoking_either_token_revokes_the_grant(client: TestClient, tokenName: str) -> None:
    tokens = login(client=client)
    assert client.post('/mcp/oauth/revoke', data={'token': tokens[tokenName]}).status_code == 200
    assert ping(client=client, accessToken=tokens['access_token']) == 401
    assert refresh(client=client, refreshToken=tokens['refresh_token'])['error'] == 'invalid_grant'


def test_revoking_an_unknown_token_succeeds(client: TestClient) -> None:
    assert client.post('/mcp/oauth/revoke', data={'token': 'garbage'}).status_code == 200


def test_client_id_metadata_documents_are_fetched_and_validated(client: TestClient, requester: FakeRequester) -> None:
    assert client.get('/mcp/oauth/authorize', params=authorize_params(clientId=CIMD_CLIENT_ID)).status_code == 200
    client.get('/mcp/oauth/authorize', params=authorize_params(clientId=CIMD_CLIENT_ID))
    assert requester.requestedUrls == [CIMD_CLIENT_ID]
    code = create_code(client=client, clientId=CIMD_CLIENT_ID)
    assert 'access_token' in exchange_code(client=client, code=code, clientId=CIMD_CLIENT_ID)


def test_client_id_metadata_documents_without_a_name_use_the_host(client: TestClient, requester: FakeRequester) -> None:
    clientId = 'https://unnamed.example/client.json'
    requester.documents[clientId] = {'client_id': clientId, 'redirect_uris': [CLIENT_REDIRECT_URI]}
    assert '<strong>unnamed.example</strong> wants to access' in client.get('/mcp/oauth/authorize', params=authorize_params(clientId=clientId)).text


@pytest.mark.parametrize(
    ('clientId', 'document'),
    [
        ('https://client.example/wrong.json', {'client_id': 'https://client.example/other.json', 'client_name': 'Wrong', 'redirect_uris': [CLIENT_REDIRECT_URI]}),
        ('https://client.example/no-redirects.json', {'client_id': 'https://client.example/no-redirects.json', 'client_name': 'No redirects', 'redirect_uris': ['https://other.example/cb']}),
        ('https://10.0.0.1/client.json', None),
        ('https://localhost/client.json', None),
        ('https://[::1]/client.json', None),
        ('https://client.example/', None),
    ],
)
def test_client_id_metadata_documents_are_rejected_when_invalid(client: TestClient, requester: FakeRequester, clientId: str, document: dict[str, object] | None) -> None:
    if document is not None:
        requester.documents[clientId] = document
    response = client.get('/mcp/oauth/authorize', params=authorize_params(clientId=clientId))
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_tokens_from_another_secret_or_expired_are_rejected(identityProvider: FakeIdentityProvider) -> None:
    oauthServer = create_oauth_server(identityProvider=identityProvider)
    otherTokens = create_oauth_server(identityProvider=identityProvider, secret='other-secret')._create_token_pair(user=McpUser(userId='user-1', userName='Test'), clientId='client', grantId='grant', grantExpiryTimestamp=2_000_000_000)
    with pytest.raises(UnauthorizedException, match='INVALID_TOKEN'):
        await oauthServer.validate_access_token(accessToken=otherTokens.accessToken)
    expiredToken = oauthServer.tokenManager.create_token(tokenType='mcpAccess', lifetime=datetime.timedelta(seconds=-1), claims={})
    with pytest.raises(UnauthorizedException, match='TOKEN_EXPIRED'):
        await oauthServer.validate_access_token(accessToken=expiredToken)


@pytest.mark.parametrize('accessToken', ['W10.e30.AA', 'e30.W10.AA', 'not-a-jwt', 'a.b.c'])
def test_malformed_tokens_are_rejected_without_a_server_error(client: TestClient, accessToken: str) -> None:
    assert client.post('/mcp', headers={'Authorization': f'Bearer {accessToken}'}, json={'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}).status_code == 401
    assert client.post('/mcp/oauth/token', data={'grant_type': 'refresh_token', 'refresh_token': accessToken}).json()['error'] == 'invalid_grant'


def test_refresh_tokens_never_outlive_the_grant(client: TestClient) -> None:
    tokens = login(client=client)
    grantExpiry = KibaJwt.from_string(jwtString=tokens['refresh_token']).payloadDict['gex']
    refreshedTokens = refresh(client=client, refreshToken=tokens['refresh_token'])
    refreshedJwt = KibaJwt.from_string(jwtString=refreshedTokens['refresh_token'])
    assert refreshedJwt.payloadDict['gex'] == grantExpiry
    assert refreshedJwt.payloadDict['exp'] <= grantExpiry


def test_consent_cookie_from_another_server_is_ignored(identityProvider: FakeIdentityProvider) -> None:
    oauthServer = create_oauth_server(identityProvider=identityProvider)
    otherServer = create_oauth_server(identityProvider=identityProvider, secret='other-secret')
    request = McpAuthorizationRequest(clientId='client', clientName='Test', redirectUri=CLIENT_REDIRECT_URI, clientState=None, codeChallenge='x' * 43)
    assert oauthServer.has_consent(consentToken=oauthServer.add_consent(consentToken=None, request=request), request=request)
    assert not oauthServer.has_consent(consentToken=otherServer.add_consent(consentToken=None, request=request), request=request)
    assert not oauthServer.has_consent(consentToken=oauthServer.add_consent(consentToken=None, request=request.model_copy(update={'redirectUri': 'https://client.example/other'})), request=request)
