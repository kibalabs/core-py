import asyncio
import pytest
from typing import Any
from collections.abc import MutableMapping

from core.exceptions import BadRequestException, NotFoundException, TooManyRequestsException
from core.requester import Requester, KibaResponse
from core.web3.eth_client import RestEthClient
from core.util.typing_util import Json


class MockResponse:
    """Mock response object that mimics httpx.Response"""

    def __init__(self, json_data: dict[str, Any], status_code: int = 200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._json_data


class MockRequester(Requester):
    """Mock requester that returns predefined responses"""

    def __init__(self, responses: dict[str, dict[str, Any]] | None = None):
        # Don't call super().__init__() to avoid creating real httpx client
        self.responses = responses or {}
        self.requests_made: list[dict[str, Any]] = []

    async def post_json(
        self,
        url: str,
        dataDict: Json | None = None,
        timeout: int | None = 10,
        headers: MutableMapping[str, str] | None = None,
        outputFilePath: str | None = None
    ) -> KibaResponse:
        # Record the request for verification
        self.requests_made.append({
            'url': url,
            'dataDict': dataDict,
            'timeout': timeout,
            'headers': headers,
        })

        # Get the method from the request
        method = dataDict.get('method') if dataDict else None

        if method in self.responses:
            response_data = self.responses[method]
            if 'error' in response_data:
                # Simulate error response
                return MockResponse(response_data, status_code=400)
            return MockResponse(response_data)

        # Default successful response
        return MockResponse({'jsonrpc': '2.0', 'result': None, 'id': None})


class TestRestEthClient:

    @pytest.fixture
    def mock_requester(self):
        return MockRequester()

    @pytest.fixture
    def client(self, mock_requester):
        return RestEthClient(
            url='https://test-rpc-url.com',
            requester=mock_requester,
            chainId=1,
            isTestnet=False
        )

    @pytest.mark.asyncio
    async def test_get_latest_block_number_success(self, client, mock_requester):
        mock_requester.responses['eth_blockNumber'] = {
            'jsonrpc': '2.0',
            'result': '0x1b4',
            'id': None
        }
        result = await client.get_latest_block_number()
        assert result == 436
        assert len(mock_requester.requests_made) == 1
        assert mock_requester.requests_made[0]['dataDict']['method'] == 'eth_blockNumber'

    @pytest.mark.asyncio
    async def test_get_latest_block_number_not_found(self, client, mock_requester):
        mock_requester.responses['eth_blockNumber'] = {
            'jsonrpc': '2.0',
            'result': None,
            'id': None
        }
        with pytest.raises(NotFoundException):
            await client.get_latest_block_number()

    @pytest.mark.asyncio
    async def test_get_block_success(self, client, mock_requester):
        mock_requester.responses['eth_getBlockByNumber'] = {
            'jsonrpc': '2.0',
            'result': {
                'number': hex(436),
                'hash': '0x1234567890abcdef',
                'parentHash': '0xabcdef1234567890',
                'timestamp': '0x12345',
                'transactions': [],
                'gasLimit': '0x1c9c380',
                'gasUsed': '0x5208',
                'baseFeePerGas': '0x7',
                'size': '0x220',
                'difficulty': '0x1',
                'totalDifficulty': '0x1',
                'extraData': '0x',
                'logsBloom': '0x' + '0' * 512,
                'miner': '0x0000000000000000000000000000000000000000',
                'mixHash': '0x' + '0' * 64,
                'nonce': '0x0000000000000000',
                'receiptsRoot': '0x' + '0' * 64,
                'sha3Uncles': '0x' + '0' * 64,
                'stateRoot': '0x' + '0' * 64,
                'transactionsRoot': '0x' + '0' * 64,
                'uncles': []
            },
            'id': None
        }
        result = await client.get_block(blockNumber=436, shouldHydrateTransactions=False)
        assert result['number'] == 436
        assert result['hash'].hex() == '1234567890abcdef'
        assert len(mock_requester.requests_made) == 1
        request = mock_requester.requests_made[0]['dataDict']
        assert request['method'] == 'eth_getBlockByNumber'
        assert request['params'] == ['0x1b4', False]

    @pytest.mark.asyncio
    async def test_get_block_not_found(self, client, mock_requester):
        mock_requester.responses['eth_getBlockByNumber'] = {
            'jsonrpc': '2.0',
            'result': None,
            'id': None
        }
        with pytest.raises(NotFoundException):
            await client.get_block(blockNumber=999999)

    @pytest.mark.asyncio
    async def test_get_block_testnet_strips_extra_data(self, mock_requester):
        client = RestEthClient(
            url='https://test-rpc-url.com',
            requester=mock_requester,
            chainId=1,
            isTestnet=True
        )
        mock_requester.responses['eth_getBlockByNumber'] = {
            'jsonrpc': '2.0',
            'result': {
                'number': hex(436),
                'hash': '0x1234567890abcdef',
                'parentHash': '0xabcdef1234567890',
                'timestamp': '0x12345',
                'transactions': [],
                'gasLimit': '0x1c9c380',
                'gasUsed': '0x5208',
                'baseFeePerGas': '0x7',
                'size': '0x220',
                'difficulty': '0x1',
                'totalDifficulty': '0x1',
                'extraData': '0x1234567890abcdef',
                'logsBloom': '0x' + '0' * 512,
                'miner': '0x0000000000000000000000000000000000000000',
                'mixHash': '0x' + '0' * 64,
                'nonce': '0x0000000000000000',
                'receiptsRoot': '0x' + '0' * 64,
                'sha3Uncles': '0x' + '0' * 64,
                'stateRoot': '0x' + '0' * 64,
                'transactionsRoot': '0x' + '0' * 64,
                'uncles': []
            },
            'id': None
        }
        result = await client.get_block(blockNumber=436)
        assert result['extraData'].hex() == '00'

    @pytest.mark.asyncio
    async def test_get_transaction_count_success(self, client, mock_requester):
        mock_requester.responses['eth_getTransactionCount'] = {
            'jsonrpc': '2.0',
            'result': hex(16),
            'id': None
        }
        result = await client.get_transaction_count(address='0x1234567890123456789012345678901234567890')
        assert result == 16
        assert len(mock_requester.requests_made) == 1
        request = mock_requester.requests_made[0]['dataDict']
        assert request['method'] == 'eth_getTransactionCount'
        assert request['params'] == ['0x1234567890123456789012345678901234567890', 'latest']

    @pytest.mark.asyncio
    async def test_get_transaction_success(self, client, mock_requester):
        mock_requester.responses['eth_getTransactionByHash'] = {
            'jsonrpc': '2.0',
            'result': {
                'hash': '0x1234567890abcdef',
                'blockHash': '0xabcdef1234567890',
                'blockNumber': hex(436),
                'from': '0x1234567890123456789012345678901234567890',
                'to': '0x0987654321098765432109876543210987654321',
                'value': hex(2000000000000000000),
                'gas': '0x5208',
                'gasPrice': '0x4a817c800',
                'input': '0x',
                'nonce': hex(16),
                'r': '0x1234567890abcdef',
                's': '0xabcdef1234567890',
                'v': '0x1b',
                'transactionIndex': '0x0',
                'type': '0x0'
            },
            'id': None
        }
        result = await client.get_transaction(transactionHash='0x1234567890abcdef')
        assert result['hash'].hex() == '1234567890abcdef'
        assert result['blockNumber'] == 436
        assert result['value'] == 2000000000000000000
        assert len(mock_requester.requests_made) == 1
        request = mock_requester.requests_made[0]['dataDict']
        assert request['method'] == 'eth_getTransactionByHash'
        assert request['params'] == ['0x1234567890abcdef']

    @pytest.mark.asyncio
    async def test_get_transaction_receipt_success(self, client, mock_requester):
        mock_requester.responses['eth_getTransactionReceipt'] = {
            'jsonrpc': '2.0',
            'result': {
                'transactionHash': '0x1234567890abcdef',
                'blockHash': '0xabcdef1234567890',
                'blockNumber': hex(436),
                'from': '0x1234567890123456789012345678901234567890',
                'to': '0x0987654321098765432109876543210987654321',
                'gasUsed': '0x5208',
                'cumulativeGasUsed': '0x5208',
                'contractAddress': None,
                'logs': [],
                'logsBloom': '0x' + '0' * 512,
                'status': '0x1',
                'transactionIndex': '0x0',
                'type': '0x0'
            },
            'id': None
        }
        result = await client.get_transaction_receipt(transactionHash='0x1234567890abcdef')
        assert result['transactionHash'].hex() == '1234567890abcdef'
        assert result['status'] == 1
        assert result['blockNumber'] == 436
        assert len(mock_requester.requests_made) == 1
        request = mock_requester.requests_made[0]['dataDict']
        assert request['method'] == 'eth_getTransactionReceipt'
        assert request['params'] == ['0x1234567890abcdef']

    @pytest.mark.asyncio
    async def test_get_log_entries_success(self, client, mock_requester):
        mock_requester.responses['eth_getLogs'] = {
            'jsonrpc': '2.0',
            'result': [
                {
                    'address': '0x1234567890123456789012345678901234567890',
                    'topics': [
                        '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                        '0x000000000000000000000000a0b86a33e6351ccede6dea8975b5e3fb6e6d9d1e',
                        '0x0000000000000000000000001234567890123456789012345678901234567890'
                    ],
                    'data': '0x0000000000000000000000000000000000000000000000000de0b6b3a7640000',
                    'blockNumber': hex(436),
                    'transactionHash': '0x1234567890abcdef',
                    'transactionIndex': '0x0',
                    'blockHash': '0xabcdef1234567890',
                    'logIndex': '0x0',
                    'removed': False
                }
            ],
            'id': None
        }
        result = await client.get_log_entries(
            topics=['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'],
            startBlockNumber=100,
            endBlockNumber=200,
            address='0x1234567890123456789012345678901234567890'
        )
        assert len(result) == 1
        assert result[0]['address'] == '0x1234567890123456789012345678901234567890'
        assert result[0]['blockNumber'] == 436
        request = mock_requester.requests_made[0]['dataDict']
        assert request['method'] == 'eth_getLogs'
        expected_params = {
            'fromBlock': hex(100),
            'toBlock': hex(200),
            'topics': ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'],
            'address': '0x1234567890123456789012345678901234567890'
        }
        assert request['params'] == [expected_params]

    @pytest.mark.asyncio
    async def test_get_log_entries_minimal_params(self, client, mock_requester):
        mock_requester.responses['eth_getLogs'] = {
            'jsonrpc': '2.0',
            'result': [],
            'id': None
        }
        result = await client.get_log_entries()
        assert result == []
        request = mock_requester.requests_made[0]['dataDict']
        assert request['method'] == 'eth_getLogs'
        assert request['params'] == [{'fromBlock': 'earliest'}]

    @pytest.mark.asyncio
    async def test_get_max_priority_fee_per_gas_success(self, client, mock_requester):
        mock_requester.responses['eth_maxPriorityFeePerGas'] = {
            'jsonrpc': '2.0',
            'result': hex(1000000000),
            'id': None
        }
        result = await client.get_max_priority_fee_per_gas()
        assert result == 1000000000
        assert len(mock_requester.requests_made) == 1
        request = mock_requester.requests_made[0]['dataDict']
        assert request['method'] == 'eth_maxPriorityFeePerGas'

    @pytest.mark.asyncio
    async def test_get_max_fee_per_gas_success(self, client, mock_requester):
        mock_requester.responses['eth_getBlockByNumber'] = {
            'jsonrpc': '2.0',
            'result': {
                'number': hex(436),
                'baseFeePerGas': hex(7),
                'hash': '0x1234567890abcdef',
                'parentHash': '0xabcdef1234567890',
                'timestamp': '0x12345',
                'transactions': [],
                'gasLimit': '0x1c9c380',
                'gasUsed': '0x5208',
                'size': '0x220',
                'difficulty': '0x1',
                'totalDifficulty': '0x1',
                'extraData': '0x',
                'logsBloom': '0x' + '0' * 512,
                'miner': '0x0000000000000000000000000000000000000000',
                'mixHash': '0x' + '0' * 64,
                'nonce': '0x0000000000000000',
                'receiptsRoot': '0x' + '0' * 64,
                'sha3Uncles': '0x' + '0' * 64,
                'stateRoot': '0x' + '0' * 64,
                'transactionsRoot': '0x' + '0' * 64,
                'uncles': []
            },
            'id': None
        }
        maxPriorityFeePerGas = 1000000000
        result = await client.get_max_fee_per_gas(maxPriorityFeePerGas=maxPriorityFeePerGas)
        expected = 7 + 1000000000
        assert result == expected
        request = mock_requester.requests_made[0]['dataDict']
        assert request['method'] == 'eth_getBlockByNumber'
        assert request['params'] == ['pending', False]

    @pytest.mark.asyncio
    async def test_get_max_fee_per_gas_with_hex_string(self, client, mock_requester):
        mock_requester.responses['eth_getBlockByNumber'] = {
            'jsonrpc': '2.0',
            'result': {
                'number': hex(436),
                'baseFeePerGas': hex(7),
                'hash': '0x1234567890abcdef',
                'parentHash': '0xabcdef1234567890',
                'timestamp': '0x12345',
                'transactions': [],
                'gasLimit': '0x1c9c380',
                'gasUsed': '0x5208',
                'size': '0x220',
                'difficulty': '0x1',
                'totalDifficulty': '0x1',
                'extraData': '0x',
                'logsBloom': '0x' + '0' * 512,
                'miner': '0x0000000000000000000000000000000000000000',
                'mixHash': '0x' + '0' * 64,
                'nonce': '0x0000000000000000',
                'receiptsRoot': '0x' + '0' * 64,
                'sha3Uncles': '0x' + '0' * 64,
                'stateRoot': '0x' + '0' * 64,
                'transactionsRoot': '0x' + '0' * 64,
                'uncles': []
            },
            'id': None
        }
        maxPriorityFeePerGas = hex(1000000000)
        result = await client.get_max_fee_per_gas(maxPriorityFeePerGas=maxPriorityFeePerGas)
        expected = 7 + 1000000000
        assert result == expected

    @pytest.mark.asyncio
    async def test_send_raw_transaction_success(self, client, mock_requester):
        mock_requester.responses['eth_sendRawTransaction'] = {
            'jsonrpc': '2.0',
            'result': '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
            'id': None
        }
        transaction_data = '0xf86c808504a817c800825208941234567890123456789012345678901234567890880de0b6b3a76400008025a01234567890abcdefa01234567890abcdefa01234567890abcdefa01234567890abcdefa01234567890abcdef'
        result = await client.send_raw_transaction(transactionData=transaction_data)
        assert result == '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef'
        request = mock_requester.requests_made[0]['dataDict']
        assert request['method'] == 'eth_sendRawTransaction'
        assert request['params'] == [transaction_data]

    @pytest.mark.asyncio
    async def test_send_raw_transaction_adds_0x_prefix(self, client, mock_requester):
        mock_requester.responses['eth_sendRawTransaction'] = {
            'jsonrpc': '2.0',
            'result': '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
            'id': None
        }
        transaction_data = 'f86c808504a817c800825208941234567890123456789012345678901234567890880de0b6b3a76400008025a01234567890abcdefa01234567890abcdefa01234567890abcdefa01234567890abcdefa01234567890abcdef'
        result = await client.send_raw_transaction(transactionData=transaction_data)
        assert result == '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef'
        request = mock_requester.requests_made[0]['dataDict']
        assert request['method'] == 'eth_sendRawTransaction'
        assert request['params'] == ['0x' + transaction_data]

    @pytest.mark.asyncio
    async def test_request_with_error_response(self, client, mock_requester):
        mock_requester.responses['eth_blockNumber'] = {
            'jsonrpc': '2.0',
            'error': {
                'code': -32602,
                'message': 'Invalid params'
            },
            'id': None
        }
        with pytest.raises(BadRequestException) as exc_info:
            await client.get_latest_block_number()
        assert 'Invalid params' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rate_limit_retry_success(self, mock_requester):
        client = RestEthClient(
            url='https://test-rpc-url.com',
            requester=mock_requester,
            chainId=1,
            shouldBackoffRetryOnRateLimit=True,
            retryLimit=2
        )
        call_count = 0
        original_post_json = mock_requester.post_json
        async def mock_post_json_with_retry(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TooManyRequestsException(message='Rate limit exceeded')
            else:
                return MockResponse({
                    'jsonrpc': '2.0',
                    'result': hex(436),
                    'id': None
                })
        mock_requester.post_json = mock_post_json_with_retry
        result = await client.get_latest_block_number()
        assert result == 436
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_rate_limit_retry_exhausted(self, mock_requester):
        client = RestEthClient(
            url='https://test-rpc-url.com',
            requester=mock_requester,
            chainId=1,
            shouldBackoffRetryOnRateLimit=True,
            retryLimit=1
        )
        async def mock_post_json_always_rate_limit(*args, **kwargs):
            raise TooManyRequestsException(message='Rate limit exceeded')
        mock_requester.post_json = mock_post_json_always_rate_limit
        with pytest.raises(TooManyRequestsException):
            await client.get_latest_block_number()

    @pytest.mark.asyncio
    async def test_rate_limit_retry_disabled(self, mock_requester):
        client = RestEthClient(
            url='https://test-rpc-url.com',
            requester=mock_requester,
            chainId=1,
            shouldBackoffRetryOnRateLimit=False
        )
        async def mock_post_json_rate_limit(*args, **kwargs):
            raise TooManyRequestsException(message='Rate limit exceeded')
        mock_requester.post_json = mock_post_json_rate_limit
        with pytest.raises(TooManyRequestsException):
            await client.get_latest_block_number()

    @pytest.mark.asyncio
    async def test_fill_transaction_params_all_provided(self, client, mock_requester):
        params = {
            'to': '0x1234567890123456789012345678901234567890',
            'from': '0x0987654321098765432109876543210987654321',
            'chainId': hex(1),
            'nonce': hex(16),
            'gas': hex(21000),
            'maxPriorityFeePerGas': hex(1000000000),
            'maxFeePerGas': hex(20000000000)
        }
        result = await client.fill_transaction_params(
            params=params.copy(),
            fromAddress='0x0987654321098765432109876543210987654321',
            nonce=16,
            gas=21000,
            maxFeePerGas=20000000000,
            maxPriorityFeePerGas=1000000000,
            chainId=1
        )
        assert result == params
        assert len(mock_requester.requests_made) == 0

    @pytest.mark.asyncio
    async def test_fill_transaction_params_fetches_missing_values(self, client, mock_requester):
        mock_requester.responses = {
            'eth_getTransactionCount': {
                'jsonrpc': '2.0',
                'result': hex(16),
                'id': None
            },
            'eth_estimateGas': {
                'jsonrpc': '2.0',
                'result': hex(21000),
                'id': None
            },
            'eth_maxPriorityFeePerGas': {
                'jsonrpc': '2.0',
                'result': hex(1000000000),
                'id': None
            },
            'eth_getBlockByNumber': {
                'jsonrpc': '2.0',
                'result': {
                    'baseFeePerGas': hex(7),
                    'number': hex(436),
                    'hash': '0x1234567890abcdef',
                    'parentHash': '0xabcdef1234567890',
                    'timestamp': '0x12345',
                    'transactions': [],
                    'gasLimit': '0x1c9c380',
                    'gasUsed': '0x5208',
                    'size': '0x220',
                    'difficulty': '0x1',
                    'totalDifficulty': '0x1',
                    'extraData': '0x',
                    'logsBloom': '0x' + '0' * 512,
                    'miner': '0x0000000000000000000000000000000000000000',
                    'mixHash': '0x' + '0' * 64,
                    'nonce': '0x0000000000000000',
                    'receiptsRoot': '0x' + '0' * 64,
                    'sha3Uncles': '0x' + '0' * 64,
                    'stateRoot': '0x' + '0' * 64,
                    'transactionsRoot': '0x' + '0' * 64,
                    'uncles': []
                },
                'id': None
            }
        }
        params = {
            'to': '0x1234567890123456789012345678901234567890',
            'from': '0x0987654321098765432109876543210987654321'
        }
        result = await client.fill_transaction_params(
            params=params,
            fromAddress='0x0987654321098765432109876543210987654321',
            chainId=1
        )
        assert result['chainId'] == hex(1)
        assert result['nonce'] == hex(16)
        assert result['gas'] == hex(21000)
        assert result['maxPriorityFeePerGas'] == hex(1000000000)
        assert result['maxFeePerGas'] == hex(7 + 1000000000)
        assert len(mock_requester.requests_made) == 4
        methods_called = [req['dataDict']['method'] for req in mock_requester.requests_made]
        assert 'eth_getTransactionCount' in methods_called
        assert 'eth_estimateGas' in methods_called
        assert 'eth_maxPriorityFeePerGas' in methods_called
        assert 'eth_getBlockByNumber' in methods_called

    @pytest.mark.asyncio
    async def test_call_function_success(self, client, mock_requester):
        mock_requester.responses['eth_call'] = {
            'jsonrpc': '2.0',
            'result': '0x000000000000000000000000000000000000000000000000000000000000007b',
            'id': None
        }
        function_abi = {
            'inputs': [],
            'name': 'getValue',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'stateMutability': 'view',
            'type': 'function'
        }
        result = await client.call_function(
            toAddress='0x1234567890123456789012345678901234567890',
            contractAbi=[function_abi],
            functionAbi=function_abi,
            fromAddress='0x0987654321098765432109876543210987654321'
        )
        assert len(result) == 1
        assert result[0] == 123
        assert len(mock_requester.requests_made) == 1
        request = mock_requester.requests_made[0]['dataDict']
        assert request['method'] == 'eth_call'
        assert request['params'][0]['to'] == '0x1234567890123456789012345678901234567890'
        assert request['params'][0]['from'] == '0x0987654321098765432109876543210987654321'
        assert request['params'][1] == 'latest'

    @pytest.mark.asyncio
    async def test_call_function_with_block_number(self, client, mock_requester):
        mock_requester.responses['eth_call'] = {
            'jsonrpc': '2.0',
            'result': '0x000000000000000000000000000000000000000000000000000000000000007b',
            'id': None
        }
        function_abi = {
            'inputs': [],
            'name': 'getValue',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'stateMutability': 'view',
            'type': 'function'
        }
        result = await client.call_function(
            toAddress='0x1234567890123456789012345678901234567890',
            contractAbi=[function_abi],
            functionAbi=function_abi,
            blockNumber=0x100
        )
        assert len(result) == 1
        assert result[0] == 123
        request = mock_requester.requests_made[0]['dataDict']
        assert request['params'][1] == hex(0x100)

    @pytest.mark.asyncio
    async def test_call_function_with_arguments(self, client, mock_requester):
        mock_requester.responses['eth_call'] = {
            'jsonrpc': '2.0',
            'result': '0x0000000000000000000000000000000000000000000000000000000000000001',
            'id': None
        }
        function_abi = {
            'inputs': [{'name': 'amount', 'type': 'uint256'}],
            'name': 'hasEnoughBalance',
            'outputs': [{'name': '', 'type': 'bool'}],
            'stateMutability': 'view',
            'type': 'function'
        }
        result = await client.call_function(
            toAddress='0x1234567890123456789012345678901234567890',
            contractAbi=[function_abi],
            functionAbi=function_abi,
            arguments={'amount': 1000}
        )
        assert result[0] is True

    @pytest.mark.asyncio
    async def test_call_function_by_name_success(self, client, mock_requester):
        mock_requester.responses['eth_call'] = {
            'jsonrpc': '2.0',
            'result': '0x000000000000000000000000000000000000000000000000000000000000007b',
            'id': None
        }
        contract_abi = [{
            'inputs': [],
            'name': 'getValue',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'stateMutability': 'view',
            'type': 'function'
        }]
        result = await client.call_function_by_name(
            toAddress='0x1234567890123456789012345678901234567890',
            contractAbi=contract_abi,
            functionName='getValue'
        )
        assert result[0] == 123

    @pytest.mark.asyncio  
    async def test_call_success(self, client, mock_requester):
        from core.web3.eth_client import ContractCall
        mock_requester.responses['eth_call'] = {
            'jsonrpc': '2.0',
            'result': '0x000000000000000000000000000000000000000000000000000000000000007b',
            'id': None
        }
        contract_abi = [{
            'inputs': [],
            'name': 'getValue',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'stateMutability': 'view',
            'type': 'function'
        }]
        contract_call = ContractCall(
            toAddress='0x1234567890123456789012345678901234567890',
            functionName='getValue',
            contractAbi=contract_abi,
            fromAddress='0x0987654321098765432109876543210987654321'
        )
        result = await client.call(contractCall=contract_call)
        assert result[0] == 123

    @pytest.mark.asyncio
    async def test_call_with_block_number(self, client, mock_requester):
        from core.web3.eth_client import ContractCall
        mock_requester.responses['eth_call'] = {
            'jsonrpc': '2.0',
            'result': '0x000000000000000000000000000000000000000000000000000000000000007b',
            'id': None
        }
        contract_abi = [{
            'inputs': [],
            'name': 'getValue',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'stateMutability': 'view',
            'type': 'function'
        }]
        contract_call = ContractCall(
            toAddress='0x1234567890123456789012345678901234567890',
            functionName='getValue',
            contractAbi=contract_abi
        )
        result = await client.call(contractCall=contract_call, blockNumber=436)
        assert result[0] == 123
        request = mock_requester.requests_made[0]['dataDict']
        assert request['params'][1] == hex(436)


    @pytest.mark.asyncio
    async def test_multicall_fallback_to_individual_calls(self, client, mock_requester):
        from core.web3.eth_client import ContractCall
        unsupported_client = RestEthClient(
            url='https://test-rpc-url.com',
            requester=mock_requester,
            chainId=999,
            isTestnet=False
        )
        call_responses = [
            '0x000000000000000000000000000000000000000000000000000000000000007b',
            '0x00000000000000000000000000000000000000000000000000000000000000c8'
        ]
        call_count = 0
        async def mock_post_json(url, dataDict, timeout=None):
            nonlocal call_count
            response_data = call_responses[call_count]
            call_count += 1
            class MockResponse:
                def json(self):
                    return {
                        'jsonrpc': '2.0',
                        'result': response_data,
                        'id': None
                    }
            return MockResponse()
        mock_requester.post_json = mock_post_json
        contract_abi = [{
            'inputs': [],
            'name': 'getValue',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'stateMutability': 'view',
            'type': 'function'
        }]
        contract_calls = [
            ContractCall(
                toAddress='0x1234567890123456789012345678901234567890',
                functionName='getValue',
                contractAbi=contract_abi
            ),
            ContractCall(
                toAddress='0x1234567890123456789012345678901234567890',
                functionName='getValue',
                contractAbi=contract_abi
            )
        ]
        result = await unsupported_client.multicall(contractCalls=contract_calls)
        assert len(result) == 2
        assert result[0][0] == 123
        assert result[1][0] == 200
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_multicall_disabled_explicitly(self, client, mock_requester):
        from core.web3.eth_client import ContractCall
        mock_requester.responses['eth_call'] = {
            'jsonrpc': '2.0',
            'result': '0x000000000000000000000000000000000000000000000000000000000000007b',
            'id': None
        }
        contract_abi = [{
            'inputs': [],
            'name': 'getValue',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'stateMutability': 'view',
            'type': 'function'
        }]
        contract_calls = [
            ContractCall(
                toAddress='0x1234567890123456789012345678901234567890',
                functionName='getValue',
                contractAbi=contract_abi
            )
        ]
        result = await client.multicall(contractCalls=contract_calls, shouldUseMulticall3=False)
        assert len(result) == 1
        assert result[0][0] == 123
        assert len(mock_requester.requests_made) == 1
        request = mock_requester.requests_made[0]['dataDict']
        assert request['params'][0]['to'] == '0x1234567890123456789012345678901234567890'

    @pytest.mark.asyncio
    async def test_call_function_empty_response_error(self, client, mock_requester):
        # Mock empty response (0x)
        mock_requester.responses['eth_call'] = {
            'jsonrpc': '2.0',
            'result': '0x',
            'id': None
        }
        function_abi = {
            'inputs': [],
            'name': 'getValue',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'stateMutability': 'view',
            'type': 'function'
        }
        with pytest.raises(BadRequestException) as exc_info:
            await client.call_function(
                toAddress='0x1234567890123456789012345678901234567890',
                contractAbi=[function_abi],
                functionAbi=function_abi
            )
        assert 'Empty response' in str(exc_info.value)
        assert 'Maybe the method does not exist on this contract' in str(exc_info.value)
