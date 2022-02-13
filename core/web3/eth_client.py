import json
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from eth_abi.exceptions import InsufficientDataBytes
from web3 import Web3
from web3._utils import method_formatters
from web3._utils.abi import get_abi_output_types
from web3._utils.contracts import encode_transaction_data
from web3.middleware import geth_poa_middleware
from web3.types import ABI
from web3.types import ABIFunction
from web3.types import BlockData
from web3.types import HexBytes
from web3.types import LogReceipt
from web3.types import TxData
from web3.types import TxReceipt

from core.exceptions import BadRequestException
from core.requester import Requester


class EthClientInterface:

    async def get_latest_block_number(self) -> int:
        raise NotImplementedError()

    async def get_block(self, blockNumber: int, shouldHydrateTransactions: bool = False) -> BlockData:
        raise NotImplementedError()

    async def get_transaction(self, transactionHash: str) -> TxData:
        raise NotImplementedError()

    async def get_transaction_receipt(self, transactionHash: str) -> TxReceipt:
        raise NotImplementedError()

    async def get_log_entries(self, topics: Optional[List[str]] = None, startBlockNumber: Optional[int] = None, endBlockNumber: Optional[int] = None, address: Optional[str] = None) -> List[LogReceipt]:
        raise NotImplementedError()

    async def call_function(self, toAddress: str, contractAbi: ABI, functionAbi: ABIFunction, fromAddress: Optional[str] = None, arguments: Optional[Dict[str, Any]] = None, blockNumber: Optional[int] = None) -> List[Any]:
        raise NotImplementedError()

    async def send_transaction(self, toAddress: str, contractAbi: ABI, functionAbi: ABIFunction, nonce: int, privateKey: str, gasPrice: int, gas: int, fromAddress: Optional[str] = None, arguments: Optional[Dict[str, Any]] = None) -> str:
        raise NotImplementedError()

class Web3EthClient(EthClientInterface):

    def __init__(self, web3Connection: Web3, isTestnet: bool = False):
        self.w3 = web3Connection
        self.isTestnet = isTestnet
        if self.isTestnet:
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    async def get_latest_block_number(self) -> int:
        return self.w3.eth.block_number

    async def get_block(self, blockNumber: int, shouldHydrateTransactions: bool = False) -> BlockData:
        return self.w3.eth.get_block(blockNumber, shouldHydrateTransactions)

    async def get_transaction_count(self, address: str) -> int:
        return self.w3.eth.get_transaction_count(address)

    async def get_transaction(self, transactionHash: str) -> TxData:
        return self.w3.eth.get_transaction(transactionHash)

    async def get_transaction_receipt(self, transactionHash: str) -> TxReceipt:
        return self.w3.eth.getTransactionReceipt(transactionHash)

    async def get_log_entries(self, topics: Optional[List[str]] = None, startBlockNumber: Optional[int] = None, endBlockNumber: Optional[int] = None, address: Optional[str] = None) -> List[LogReceipt]:
        contractFilter = self.w3.eth.filter({
            'fromBlock': startBlockNumber,
            'toBlock': endBlockNumber,
            'topics': topics,
            'address': address,
        })
        return contractFilter.get_all_entries()

    async def call_function(self, toAddress: str, contractAbi: ABI, functionAbi: ABIFunction, fromAddress: Optional[str] = None, arguments: Optional[Dict[str, Any]] = None, blockNumber: Optional[int] = None) -> List[Any]:
        raise NotImplementedError()

    async def send_transaction(self, toAddress: str, contractAbi: ABI, functionAbi: ABIFunction, nonce: int, privateKey: str, gasPrice: int, gas: int, fromAddress: Optional[str] = None, arguments: Optional[Dict[str, Any]] = None) -> str:
        raise NotImplementedError()

class RestEthClient(EthClientInterface):

    #NOTE(krishan711): find docs at https://eth.wiki/json-rpc/API
    def __init__(self, url: str, requester: Requester, isTestnet: bool = False):
        self.url = url
        self.requester = requester
        self.isTestnet = isTestnet
        self.w3 = Web3()

    @staticmethod
    def _hex_to_int(value: str) -> int:
        return int(value, 16)

    async def _make_request(self, method: str, params: List = None) -> Dict:
        response = await self.requester.post_json(url=self.url, dataDict={'jsonrpc':'2.0', 'method': method, 'params': params or [], 'id': 0}, timeout=100)
        jsonResponse = response.json()
        if jsonResponse.get('error'):
            raise BadRequestException(message=jsonResponse['error'].get('message') or jsonResponse['error'].get('details') or json.dumps(jsonResponse['error']))
        return jsonResponse

    async def get_latest_block_number(self) -> int:
        response = await self._make_request(method='eth_blockNumber')
        return method_formatters.PYTHONIC_RESULT_FORMATTERS['eth_blockNumber'](response['result'])

    async def get_block(self, blockNumber: int, shouldHydrateTransactions: bool = False) -> BlockData:
        response = await self._make_request(method='eth_getBlockByNumber', params=[hex(blockNumber), shouldHydrateTransactions])
        if self.isTestnet:
            # NOTE(krishan711): In testnet strip out the extra data as done by web3
            # https://web3py.readthedocs.io/en/stable/middleware.html#why-is-geth-poa-middleware-necessary
            response['result']['extraData'] = HexBytes('0').hex()
        return method_formatters.PYTHONIC_RESULT_FORMATTERS['eth_getBlockByNumber'](response['result'])

    async def get_transaction_count(self, address: str) -> TxData:
        response = await self._make_request(method='eth_getTransactionCount', params=[address, 'latest'])
        return method_formatters.PYTHONIC_RESULT_FORMATTERS['eth_getTransactionCount'](response['result'])

    async def get_transaction(self, transactionHash: str) -> TxData:
        response = await self._make_request(method='eth_getTransactionByHash', params=[transactionHash])
        return method_formatters.PYTHONIC_RESULT_FORMATTERS['eth_getTransactionByHash'](response['result'])

    async def get_transaction_receipt(self, transactionHash: str) -> TxReceipt:
        response = await self._make_request(method='eth_getTransactionReceipt', params=[transactionHash])
        return method_formatters.PYTHONIC_RESULT_FORMATTERS['eth_getTransactionReceipt'](response['result'])

    async def get_log_entries(self, topics: Optional[List[str]] = None, startBlockNumber: Optional[int] = None, endBlockNumber: Optional[int] = None, address: Optional[str] = None) -> List[LogReceipt]:
        params = {
            'fromBlock': 'earliest',
        }
        if topics:
            params['topics'] = topics
        if startBlockNumber:
            params['fromBlock'] = hex(startBlockNumber)
        if endBlockNumber:
            params['toBlock'] = hex(endBlockNumber)
        if address:
            params['address'] = address
        response = await self._make_request(method='eth_getLogs', params=[params])
        return method_formatters.PYTHONIC_RESULT_FORMATTERS['eth_getLogs'](response['result'])

    async def call_function(self, toAddress: str, contractAbi: ABI, functionAbi: ABIFunction, fromAddress: Optional[str] = None, arguments: Optional[Dict[str, Any]] = None, blockNumber: Optional[int] = None) -> List[Any]:
        data = encode_transaction_data(web3=self.w3, fn_identifier=functionAbi['name'], contract_abi=contractAbi, fn_abi=functionAbi, kwargs=(arguments or {}))
        params = {
            'from': fromAddress or '0x0000000000000000000000000000000000000000',
            'to': toAddress,
            'data': data,
        }
        response = await self._make_request(method='eth_call', params=[params, blockNumber or 'latest'])
        outputTypes = get_abi_output_types(abi=functionAbi)
        try:
            outputData = self.w3.codec.decode_abi(types=outputTypes, data=HexBytes(response['result']))
        except InsufficientDataBytes as exception:
            if response['result'] == '0x':
                raise BadRequestException(f'Empty response: {str(exception)}. Maybe the method does not exist on this contract.')
            raise exception
        return list(outputData)

    def get_transaction_params(self, toAddress: str, contractAbi: ABI, functionAbi: ABIFunction, nonce: int, gasPrice: int = 2000000000000, gas: int = 90000, fromAddress: Optional[str] = None, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        data = encode_transaction_data(web3=self.w3, fn_identifier=functionAbi['name'], contract_abi=contractAbi, fn_abi=functionAbi, kwargs=(arguments or {}))
        params = {
            'from': fromAddress or '0x0000000000000000000000000000000000000000',
            'to': toAddress,
            'data': data,
            'gas': gas,
            'gasPrice': gasPrice,
            'nonce': nonce,
        }
        return params

    async def send_raw_transaction(self, transactionData: str) -> str:
        response = await self._make_request(method='eth_sendRawTransaction', params=[transactionData])
        return response['result']

    async def send_transaction(self, toAddress: str, contractAbi: ABI, functionAbi: ABIFunction, nonce: int, privateKey: str, gasPrice: int = 2000000000000, gas: int = 90000, fromAddress: Optional[str] = None, arguments: Optional[Dict[str, Any]] = None) -> str:
        params = self.get_transaction_params(toAddress=toAddress, contractAbi=contractAbi, functionAbi=functionAbi, nonce=nonce, gasPrice=gasPrice, gas=gas, fromAddress=fromAddress, arguments=arguments)
        signedParams = self.w3.eth.account.sign_transaction(transaction_dict=params, private_key=privateKey)
        output = await self.send_raw_transaction(transactionData=signedParams.rawTransaction.hex())
        return output
