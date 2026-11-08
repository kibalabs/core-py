import hmac
import html
import secrets
import urllib.parse

from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.responses import JSONResponse
from starlette.responses import PlainTextResponse
from starlette.responses import RedirectResponse
from starlette.responses import Response
from starlette.routing import Route

from core.api.request_body import read_request_body
from core.exceptions import BadRequestException
from core.exceptions import ForbiddenException
from core.exceptions import UnauthorizedException
from core.mcp.mcp_oauth_server import McpOAuthServer
from core.mcp.mcp_server import McpServer
from core.mcp.model import McpAuthorizationRequest

DEFAULT_MAX_BODY_BYTES = 4 * 1024 * 1024
CONSENT_COOKIE_NAME = '__Host-mcp-consent'
CSRF_COOKIE_NAME = '__Host-mcp-csrf'
STATE_COOKIE_NAME = '__Host-mcp-state'
CONSENT_PAGE_HEADERS = {
    'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
    'X-Frame-Options': 'DENY',
    'Cache-Control': 'no-store',
}


def create_mcp_routes(mcpServer: McpServer, oauthServer: McpOAuthServer, resourceName: str, allowedOrigins: list[str] | None = None, maxBodyBytes: int = DEFAULT_MAX_BODY_BYTES) -> list[Route]:
    mcpPath = oauthServer.mcpPath
    protectedResourceMetadataUrl = f'{oauthServer.baseUrl}/.well-known/oauth-protected-resource'
    parsedBaseUrl = urllib.parse.urlparse(oauthServer.baseUrl)
    validOrigins = set(allowedOrigins) if allowedOrigins is not None else {f'{parsedBaseUrl.scheme}://{parsedBaseUrl.netloc}'}

    async def get_protected_resource_metadata(request: Request) -> Response:  # noqa: ARG001
        return JSONResponse(oauthServer.get_protected_resource_metadata(resourceName=resourceName))

    async def get_authorization_server_metadata(request: Request) -> Response:  # noqa: ARG001
        return JSONResponse(oauthServer.get_authorization_server_metadata())

    async def register_client(request: Request) -> Response:
        body = await read_request_body(request=request)
        redirectUris = body.get('redirect_uris')
        clientName = body.get('client_name')
        if not isinstance(redirectUris, list) or not all(isinstance(redirectUri, str) for redirectUri in redirectUris):
            return _oauth_error(error='invalid_redirect_uri', description='redirect_uris must be a list of strings')
        try:
            registration = oauthServer.register_client(redirectUris=[str(redirectUri) for redirectUri in redirectUris], clientName=clientName if isinstance(clientName, str) else None)
        except BadRequestException:
            return _oauth_error(error='invalid_redirect_uri', description='redirect_uri is not allowed')
        return JSONResponse(registration, status_code=201, headers={'Cache-Control': 'no-store'})

    async def authorize(request: Request) -> Response:
        queryParams = request.query_params
        try:
            authorizationRequest = await oauthServer.create_authorization_request(
                clientId=queryParams.get('client_id', ''),
                redirectUri=queryParams.get('redirect_uri', ''),
                responseType=queryParams.get('response_type'),
                clientState=queryParams.get('state'),
                codeChallenge=queryParams.get('code_challenge', ''),
                codeChallengeMethod=queryParams.get('code_challenge_method'),
                resource=queryParams.get('resource'),
            )
        except BadRequestException as exception:
            return PlainTextResponse(f'Invalid authorization request: {exception.message}', status_code=400)
        if oauthServer.has_consent(consentToken=request.cookies.get(CONSENT_COOKIE_NAME), request=authorizationRequest):
            return start_provider_login(authorizationRequest=authorizationRequest, statusCode=302)
        csrfToken = secrets.token_urlsafe(32)
        response = HTMLResponse(
            _render_consent_page(consentRequestToken=oauthServer.create_consent_request_token(request=authorizationRequest), csrfToken=csrfToken, request=authorizationRequest, resourceName=resourceName, consentPath=f'{mcpPath}/oauth/consent'),
            headers=CONSENT_PAGE_HEADERS,
        )
        _set_cookie(response=response, name=CSRF_COOKIE_NAME, value=csrfToken, maxAgeSeconds=int(oauthServer.stateTokenLifetime.total_seconds()))
        return response

    async def consent(request: Request) -> Response:
        body = await read_request_body(request=request)
        csrfCookie = request.cookies.get(CSRF_COOKIE_NAME)
        csrfToken = body.get('csrf_token')
        if not csrfCookie or not isinstance(csrfToken, str) or not hmac.compare_digest(csrfCookie, csrfToken):
            return PlainTextResponse('Consent request expired or did not come from this browser. Start the connection again from your MCP client.', status_code=403)
        try:
            authorizationRequest = oauthServer.get_consent_request(consentRequestToken=str(body.get('consent_request', '')))
        except BadRequestException:
            return PlainTextResponse('Consent request expired. Start the connection again from your MCP client.', status_code=400)
        if body.get('decision') != 'approve':
            response: Response = RedirectResponse(url=oauthServer.create_client_error_redirect(request=authorizationRequest, error='access_denied'), status_code=303)
        else:
            response = start_provider_login(authorizationRequest=authorizationRequest, statusCode=303)
            _set_cookie(response=response, name=CONSENT_COOKIE_NAME, value=oauthServer.add_consent(consentToken=request.cookies.get(CONSENT_COOKIE_NAME), request=authorizationRequest), maxAgeSeconds=int(oauthServer.consentLifetime.total_seconds()))
        response.delete_cookie(key=CSRF_COOKIE_NAME, path='/', secure=True, httponly=True, samesite='lax')
        return response

    def start_provider_login(authorizationRequest: McpAuthorizationRequest, statusCode: int) -> Response:
        providerLogin = oauthServer.start_provider_login(request=authorizationRequest)
        response = RedirectResponse(url=providerLogin.authorizeUrl, status_code=statusCode)
        _set_cookie(response=response, name=STATE_COOKIE_NAME, value=providerLogin.stateNonce, maxAgeSeconds=int(oauthServer.stateTokenLifetime.total_seconds()))
        return response

    async def provider_callback(request: Request) -> Response:
        queryParams = request.query_params
        try:
            clientRedirectUrl = await oauthServer.complete_provider_login(providerCode=queryParams.get('code'), stateToken=queryParams.get('state', ''), stateNonce=request.cookies.get(STATE_COOKIE_NAME))
        except BadRequestException as exception:
            return PlainTextResponse(f'Login failed: {exception.message}. Start the connection again from your MCP client.', status_code=400)
        response = RedirectResponse(url=clientRedirectUrl, status_code=302)
        response.delete_cookie(key=STATE_COOKIE_NAME, path='/', secure=True, httponly=True, samesite='lax')
        return response

    async def token(request: Request) -> Response:
        body = await read_request_body(request=request)
        grantType = body.get('grant_type')
        resource = body.get('resource')
        clientId = body.get('client_id')
        try:
            if grantType == 'authorization_code':
                tokenPair = await oauthServer.exchange_authorization_code(
                    code=str(body.get('code', '')),
                    codeVerifier=str(body.get('code_verifier', '')),
                    redirectUri=str(body.get('redirect_uri', '')),
                    clientId=str(clientId or ''),
                    resource=resource if isinstance(resource, str) else None,
                )
            elif grantType == 'refresh_token':
                tokenPair = await oauthServer.refresh_tokens(refreshToken=str(body.get('refresh_token', '')), clientId=clientId if isinstance(clientId, str) else None, resource=resource if isinstance(resource, str) else None)
            else:
                return _oauth_error(error='unsupported_grant_type', description='grant_type must be authorization_code or refresh_token')
        except (UnauthorizedException, ForbiddenException) as exception:
            return _oauth_error(error='invalid_target' if exception.message == 'INVALID_TARGET' else 'invalid_grant', description=exception.message or 'invalid grant')
        return JSONResponse(
            {'access_token': tokenPair.accessToken, 'token_type': 'Bearer', 'expires_in': tokenPair.expiresInSeconds, 'refresh_token': tokenPair.refreshToken},
            headers={'Cache-Control': 'no-store'},
        )

    async def revoke(request: Request) -> Response:
        body = await read_request_body(request=request)
        tokenValue = body.get('token')
        if not isinstance(tokenValue, str):
            return _oauth_error(error='invalid_request', description='token is required')
        await oauthServer.revoke_token(token=tokenValue)
        return Response(status_code=200, headers={'Cache-Control': 'no-store'})

    async def handle_mcp(request: Request) -> Response:
        origin = request.headers.get('Origin')
        if origin is not None and origin not in validOrigins:
            return JSONResponse({'jsonrpc': '2.0', 'error': {'code': -32600, 'message': 'Origin not allowed'}}, status_code=403)
        scheme, _, accessToken = request.headers.get('Authorization', '').partition(' ')
        if scheme.lower() != 'bearer' or not accessToken:
            return Response(status_code=401, headers={'WWW-Authenticate': f'Bearer resource_metadata="{protectedResourceMetadataUrl}"'})
        try:
            user = await oauthServer.validate_access_token(accessToken=accessToken)
        except UnauthorizedException as exception:
            return Response(status_code=401, headers={'WWW-Authenticate': f'Bearer error="invalid_token", error_description="{exception.message}", resource_metadata="{protectedResourceMetadataUrl}"'})
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > maxBodyBytes:
                return Response(status_code=413)
        mcpResponse = await mcpServer.handle_http_message(body=bytes(body), headers=request.headers, user=user)
        if mcpResponse.body is None:
            return Response(status_code=mcpResponse.statusCode)
        return JSONResponse(mcpResponse.body, status_code=mcpResponse.statusCode)

    async def reject_mcp_stream(request: Request) -> Response:  # noqa: ARG001
        return Response(status_code=405, headers={'Allow': 'POST'})

    return [
        Route('/.well-known/oauth-protected-resource', get_protected_resource_metadata, methods=['GET']),
        Route(f'/.well-known/oauth-protected-resource{mcpPath}', get_protected_resource_metadata, methods=['GET']),
        Route('/.well-known/oauth-authorization-server', get_authorization_server_metadata, methods=['GET']),
        Route(f'{mcpPath}/oauth/register', register_client, methods=['POST']),
        Route(f'{mcpPath}/oauth/authorize', authorize, methods=['GET']),
        Route(f'{mcpPath}/oauth/consent', consent, methods=['POST']),
        Route(f'{mcpPath}/oauth/callback', provider_callback, methods=['GET']),
        Route(f'{mcpPath}/oauth/token', token, methods=['POST']),
        Route(f'{mcpPath}/oauth/revoke', revoke, methods=['POST']),
        Route(mcpPath, handle_mcp, methods=['POST']),
        Route(mcpPath, reject_mcp_stream, methods=['GET', 'DELETE']),
    ]


def _render_consent_page(consentRequestToken: str, csrfToken: str, request: McpAuthorizationRequest, resourceName: str, consentPath: str) -> str:
    redirectHost = urllib.parse.urlparse(request.redirectUri).netloc
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Connect {html.escape(request.clientName)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:32rem;margin:4rem auto;padding:0 1rem;line-height:1.5}}code{{word-break:break-all}}button{{font-size:1rem;padding:.5rem 1rem;margin-right:.5rem}}</style></head>
<body>
<h1>Connect {html.escape(request.clientName)}?</h1>
<p><strong>{html.escape(request.clientName)}</strong> wants to access <strong>{html.escape(resourceName)}</strong> as you.</p>
<p>After you sign in, access will be sent to <strong>{html.escape(redirectHost)}</strong> (<code>{html.escape(request.redirectUri)}</code>). Only continue if you started this connection yourself.</p>
<form method="post" action="{html.escape(consentPath)}">
<input type="hidden" name="consent_request" value="{html.escape(consentRequestToken)}">
<input type="hidden" name="csrf_token" value="{html.escape(csrfToken)}">
<button type="submit" name="decision" value="approve">Allow</button>
<button type="submit" name="decision" value="deny">Deny</button>
</form>
</body>
</html>
"""


def _set_cookie(response: Response, name: str, value: str, maxAgeSeconds: int) -> None:
    response.set_cookie(key=name, value=value, max_age=maxAgeSeconds, path='/', secure=True, httponly=True, samesite='lax')


def _oauth_error(error: str, description: str) -> Response:
    return JSONResponse({'error': error, 'error_description': description}, status_code=400, headers={'Cache-Control': 'no-store'})
