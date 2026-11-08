import base64

import pytest
from starlette.testclient import TestClient

from tests.mcp.conftest import BASE_URL
from tests.mcp.conftest import CLIENT_CAPABILITIES
from tests.mcp.conftest import login


@pytest.fixture
def accessToken(client: TestClient) -> str:
    return login(client=client, userId='user-1')['access_token']


def post_legacy(client: TestClient, accessToken: str, message: object, protocolVersion: str | None = '2025-11-25'):
    headers = {'Authorization': f'Bearer {accessToken}'}
    if protocolVersion:
        headers['MCP-Protocol-Version'] = protocolVersion
    return client.post('/mcp', headers=headers, json=message)


def post_modern(client: TestClient, accessToken: str, method: str, params: dict[str, object] | None = None, headers: dict[str, str] | None = None, meta: dict[str, object] | None = None):
    requestHeaders = {'Authorization': f'Bearer {accessToken}', 'MCP-Protocol-Version': '2026-07-28', 'Mcp-Method': method}
    if params and 'name' in params:
        requestHeaders['Mcp-Name'] = str(params['name'])
    requestHeaders.update(headers or {})
    return client.post('/mcp', headers=requestHeaders, json={'jsonrpc': '2.0', 'id': 7, 'method': method, 'params': {**(params or {}), '_meta': meta if meta is not None else CLIENT_CAPABILITIES}})


def test_legacy_initialize_negotiates_a_legacy_version(client: TestClient, accessToken: str) -> None:
    result = post_legacy(client=client, accessToken=accessToken, protocolVersion=None, message={'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}}).json()['result']
    assert result['protocolVersion'] == '2025-06-18'
    assert result['instructions'] == 'Use the tools.'
    unknownVersionResult = post_legacy(client=client, accessToken=accessToken, protocolVersion=None, message={'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2099-01-01'}}).json()['result']
    assert unknownVersionResult['protocolVersion'] == '2025-11-25'


def test_legacy_tool_calls_run_as_the_logged_in_user(client: TestClient, accessToken: str) -> None:
    tools = post_legacy(client=client, accessToken=accessToken, message={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}).json()['result']['tools']
    assert [tool['name'] for tool in tools] == ['echo', 'echo_structured', 'whoami']
    assert tools[0]['inputSchema']['required'] == ['text']
    assert 'outputSchema' in tools[1]
    result = post_legacy(client=client, accessToken=accessToken, message={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'echo', 'arguments': {'text': 'hi'}}}).json()['result']
    assert result == {'content': [{'type': 'text', 'text': 'user-1: hi'}], 'isError': False}


def test_structured_tool_results_include_structured_content(client: TestClient, accessToken: str) -> None:
    result = post_legacy(client=client, accessToken=accessToken, message={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'echo_structured', 'arguments': {'text': 'hi'}}}).json()['result']
    assert result['structuredContent'] == {'userId': 'user-1', 'text': 'hi'}
    assert result['isError'] is False


@pytest.mark.parametrize(
    ('toolName', 'arguments', 'expectedText'),
    [('echo', {'text': 'fail'}, 'echo failed'), ('echo', {'other': 'x'}, 'Invalid arguments'), ('whoami', {'unexpected': 1}, 'Invalid arguments'), ('missing', {}, 'Unknown tool: missing')],
)
def test_tool_failures_are_returned_as_tool_errors(client: TestClient, accessToken: str, toolName: str, arguments: dict[str, object], expectedText: str) -> None:
    result = post_legacy(client=client, accessToken=accessToken, message={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': toolName, 'arguments': arguments}}).json()['result']
    assert result['isError'] is True
    assert expectedText in result['content'][0]['text']


def test_legacy_notifications_and_batches(client: TestClient, accessToken: str) -> None:
    assert post_legacy(client=client, accessToken=accessToken, message={'jsonrpc': '2.0', 'method': 'notifications/initialized'}).status_code == 202
    batchResponse = post_legacy(
        client=client,
        accessToken=accessToken,
        protocolVersion='2025-03-26',
        message=[{'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, {'jsonrpc': '2.0', 'method': 'notifications/initialized'}, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'arguments': {}}}, {'jsonrpc': '2.0', 'id': 3, 'method': 'nope'}],
    )
    assert [item['id'] for item in batchResponse.json()] == [1, 2, 3]
    assert [item.get('error', {}).get('code') for item in batchResponse.json()] == [None, -32602, -32601]
    assert post_legacy(client=client, accessToken=accessToken, message=[]).status_code == 400


def test_legacy_rejects_an_unsupported_protocol_version_header(client: TestClient, accessToken: str) -> None:
    response = post_legacy(client=client, accessToken=accessToken, protocolVersion='2024-11-05', message={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
    assert response.status_code == 400


def test_modern_discover_and_list_include_caching_and_server_info(client: TestClient, accessToken: str) -> None:
    discoverResult = post_modern(client=client, accessToken=accessToken, method='server/discover').json()['result']
    assert discoverResult['supportedVersions'] == ['2026-07-28', '2025-11-25', '2025-06-18', '2025-03-26']
    assert discoverResult['resultType'] == 'complete'
    assert discoverResult['instructions'] == 'Use the tools.'
    assert discoverResult['_meta']['io.modelcontextprotocol/serverInfo'] == {'name': 'test-server', 'version': '1.0'}
    listResult = post_modern(client=client, accessToken=accessToken, method='tools/list').json()['result']
    assert (listResult['ttlMs'], listResult['cacheScope'], listResult['resultType']) == (60_000, 'public', 'complete')


def test_modern_tool_call_validates_the_name_header(client: TestClient, accessToken: str) -> None:
    params = {'name': 'echo', 'arguments': {'text': 'hi'}}
    assert post_modern(client=client, accessToken=accessToken, method='tools/call', params=params).json()['result']['content'][0]['text'] == 'user-1: hi'
    encodedName = '=?base64?' + base64.b64encode(b'echo').decode() + '?='
    assert post_modern(client=client, accessToken=accessToken, method='tools/call', params=params, headers={'Mcp-Name': encodedName}).status_code == 200
    mismatchResponse = post_modern(client=client, accessToken=accessToken, method='tools/call', params=params, headers={'Mcp-Name': 'whoami'})
    assert mismatchResponse.status_code == 400
    assert mismatchResponse.json()['error']['code'] == -32020


@pytest.mark.parametrize('headers', [{'Mcp-Method': 'tools/call'}, {'MCP-Protocol-Version': '2025-11-25'}])
def test_modern_rejects_headers_that_do_not_match_the_body(client: TestClient, accessToken: str, headers: dict[str, str]) -> None:
    response = post_modern(client=client, accessToken=accessToken, method='tools/list', headers=headers)
    assert response.status_code == 400
    assert response.json()['error']['code'] == -32020


def test_modern_rejects_an_unsupported_version_with_the_supported_list(client: TestClient, accessToken: str) -> None:
    response = post_modern(client=client, accessToken=accessToken, method='tools/list', headers={'MCP-Protocol-Version': '2099-01-01'}, meta={'io.modelcontextprotocol/protocolVersion': '2099-01-01', 'io.modelcontextprotocol/clientCapabilities': {}})
    assert response.status_code == 400
    assert response.json()['error']['code'] == -32022
    assert response.json()['error']['data'] == {'supported': ['2026-07-28', '2025-11-25', '2025-06-18', '2025-03-26'], 'requested': '2099-01-01'}


def test_modern_requires_client_capabilities(client: TestClient, accessToken: str) -> None:
    response = post_modern(client=client, accessToken=accessToken, method='tools/list', meta={'io.modelcontextprotocol/protocolVersion': '2026-07-28'})
    assert response.status_code == 400
    assert response.json()['error']['code'] == -32602


@pytest.mark.parametrize('method', ['initialize', 'ping', 'resources/list'])
def test_modern_unknown_methods_are_404(client: TestClient, accessToken: str, method: str) -> None:
    response = post_modern(client=client, accessToken=accessToken, method=method)
    assert response.status_code == 404
    assert response.json()['error']['code'] == -32601


@pytest.mark.parametrize('authorization', [None, 'Bearer not-a-token', 'Basic abc'])
def test_mcp_requires_a_valid_access_token(client: TestClient, authorization: str | None) -> None:
    response = client.post('/mcp', headers={'Authorization': authorization} if authorization else {}, json={'jsonrpc': '2.0', 'id': 1, 'method': 'ping'})
    assert response.status_code == 401
    assert f'resource_metadata="{BASE_URL}/.well-known/oauth-protected-resource"' in response.headers['www-authenticate']


def test_mcp_rejects_foreign_origins_and_large_bodies(client: TestClient, accessToken: str) -> None:
    headers = {'Authorization': f'Bearer {accessToken}'}
    assert client.post('/mcp', headers={**headers, 'Origin': 'https://evil.example'}, json={'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}).status_code == 403
    assert client.post('/mcp', headers={**headers, 'Origin': BASE_URL}, json={'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}).status_code == 200
    assert client.post('/mcp', headers=headers, json={'jsonrpc': '2.0', 'id': 1, 'method': 'ping', 'params': {'padding': 'x' * 20_000}}).status_code == 413


def test_mcp_rejects_invalid_json(client: TestClient, accessToken: str) -> None:
    response = client.post('/mcp', headers={'Authorization': f'Bearer {accessToken}', 'Content-Type': 'application/json'}, content=b'{not json')
    assert response.status_code == 400
    assert response.json()['error']['code'] == -32700
