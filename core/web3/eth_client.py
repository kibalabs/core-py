import asyncio
import json
import typing
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from eth_abi.exceptions import DecodingError
from eth_abi.exceptions import InsufficientDataBytes
from eth_typing import ABI
from eth_typing import ABIFunction
from eth_utils.abi import get_abi_output_types
from web3 import Web3
from web3._utils import method_formatters
from web3._utils.contracts import encode_transaction_data
from web3._utils.rpc_abi import RPC
from web3.types import BlockData
from web3.types import HexBytes
from web3.types import HexStr
from web3.types import LogReceipt
from web3.types import TxData
from web3.types import TxReceipt

from core.exceptions import BadRequestException
from core.exceptions import NotFoundException
from core.requester import Requester
from core.util import chain_util

ListAny = List[Any]  # type: ignore[misc]
DictStrAny = Dict[str, Any]  # type: ignore[misc]


class EthClientInterface:

    async def get_latest_block_number(self) -> int:
        raise NotImplementedError()

    async def get_block(self, blockNumber: int, shouldHydrateTransactions: bool = False) -> BlockData:
        raise NotImplementedError()

    async def get_block_uncle_count(self, blockNumber: int) -> int:
        raise NotImplementedError()

    async def get_transaction(self, transactionHash: str) -> TxData:
        raise NotImplementedError()

    async def get_transaction_receipt(self, transactionHash: str) -> TxReceipt:
        raise NotImplementedError()

    async def get_log_entries(self, topics: Optional[List[str]] = None, startBlockNumber: Optional[int] = None, endBlockNumber: Optional[int] = None, address: Optional[str] = None) -> List[LogReceipt]:
        raise NotImplementedError()

    async def call_function(self, toAddress: str, contractAbi: ABI, functionAbi: ABIFunction, fromAddress: Optional[str] = None, arguments: Optional[DictStrAny] = None, blockNumber: Optional[int] = None) -> ListAny:
        raise NotImplementedError()

    async def call_function_by_name(self, toAddress: str, contractAbi: ABI, functionName: str, fromAddress: Optional[str] = None, arguments: Optional[DictStrAny] = None, blockNumber: Optional[int] = None) -> ListAny:
        raise NotImplementedError()

    async def send_raw_transaction(self, transactionData: str) -> str:
        raise NotImplementedError()

    async def send_transaction(self, toAddress: str, contractAbi: ABI, functionAbi: ABIFunction, privateKey: str, fromAddress: str, nonce: Optional[int] = None, gas: Optional[int] = None, maxFeePerGas: Optional[int] = None, maxPriorityFeePerGas: Optional[int] = None, arguments: Optional[DictStrAny] = None, chainId: Optional[int] = None) -> str:
        raise NotImplementedError()

    async def send_transaction_by_name(self, toAddress: str, contractAbi: ABI, functionName: str, privateKey: str, fromAddress: str, nonce: Optional[int] = None, gas: Optional[int] = None, maxFeePerGas: Optional[int] = None, maxPriorityFeePerGas: Optional[int] = None, arguments: Optional[DictStrAny] = None, chainId: Optional[int] = None) -> str:
        raise NotImplementedError()

    async def wait_for_transaction_receipt(self, transactionHash: str, sleepSeconds: int = 2) -> TxReceipt:
        raise NotImplementedError()


class Web3EthClient(EthClientInterface):

    def __init__(self, web3Connection: Web3, isTestnet: bool = False):
        self.w3 = web3Connection
        self.isTestnet = isTestnet
        # if self.isTestnet:
        #     self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    async def get_latest_block_number(self) -> int:
        return self.w3.eth.block_number

    async def get_block(self, blockNumber: int, shouldHydrateTransactions: bool = False) -> BlockData:
        return self.w3.eth.get_block(blockNumber, shouldHydrateTransactions)

    async def get_block_uncle_count(self, blockNumber: int) -> int:
        return self.w3.eth.get_uncle_count(blockNumber)

    async def get_transaction_count(self, address: str) -> int:
        return self.w3.eth.get_transaction_count(chain_util.normalize_address_checksum(value=address))

    async def get_transaction(self, transactionHash: str) -> TxData:
        return self.w3.eth.get_transaction(typing.cast(HexStr, transactionHash))

    async def get_transaction_receipt(self, transactionHash: str) -> TxReceipt:
        return self.w3.eth.get_transaction_receipt(typing.cast(HexStr, transactionHash))

    async def get_log_entries(self, topics: Optional[List[str]] = None, startBlockNumber: Optional[int] = None, endBlockNumber: Optional[int] = None, address: Optional[str] = None) -> List[LogReceipt]:
        contractFilter = self.w3.eth.filter({
            'fromBlock': startBlockNumber,  # type: ignore[typeddict-item]
            'toBlock': endBlockNumber,  # type: ignore[typeddict-item]
            'topics': topics,  # type: ignore[typeddict-item]
            'address': address,  # type: ignore[typeddict-item]
        })
        return contractFilter.get_all_entries()

    async def call_function(self, toAddress: str, contractAbi: ABI, functionAbi: ABIFunction, fromAddress: Optional[str] = None, arguments: Optional[DictStrAny] = None, blockNumber: Optional[int] = None) -> ListAny:
        raise NotImplementedError()

    async def call_function_by_name(self, toAddress: str, contractAbi: ABI, functionName: str, fromAddress: Optional[str] = None, arguments: Optional[DictStrAny] = None, blockNumber: Optional[int] = None) -> ListAny:
        raise NotImplementedError()

    async def send_raw_transaction(self, transactionData: str) -> str:
        raise NotImplementedError()

    async def send_transaction(self, toAddress: str, contractAbi: ABI, functionAbi: ABIFunction, privateKey: str, fromAddress: str, nonce: Optional[int] = None, gas: Optional[int] = None, maxFeePerGas: Optional[int] = None, maxPriorityFeePerGas: Optional[int] = None, arguments: Optional[DictStrAny] = None, chainId: Optional[int] = None) -> str:
        raise NotImplementedError()

    async def send_transaction_by_name(self, toAddress: str, contractAbi: ABI, functionName: str, privateKey: str, fromAddress: str, nonce: Optional[int] = None, gas: Optional[int] = None, maxFeePerGas: Optional[int] = None, maxPriorityFeePerGas: Optional[int] = None, arguments: Optional[DictStrAny] = None, chainId: Optional[int] = None) -> str:
        raise NotImplementedError()

    async def wait_for_transaction_receipt(self, transactionHash: str, sleepSeconds: int = 2) -> TxReceipt:
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

    async def _make_request(self, method: str, params: Optional[ListAny] = None) -> Any:  # type: ignore[misc]
        response = await self.requester.post_json(url=self.url, dataDict={'jsonrpc':'2.0', 'method': method, 'params': params or [], 'id': 0}, timeout=100)
        jsonResponse = response.json()
        if jsonResponse.get('error'):
            print('jsonResponse', jsonResponse)
            raise BadRequestException(message=jsonResponse['error'].get('message') or jsonResponse['error'].get('details') or json.dumps(jsonResponse['error']))
        return jsonResponse

    async def get_latest_block_number(self) -> int:
        response = await self._make_request(method='eth_blockNumber')
        if response['result'] is None:
            raise NotFoundException()
        return typing.cast(int, method_formatters.PYTHONIC_RESULT_FORMATTERS[RPC.eth_blockNumber](response['result']))

    async def get_block(self, blockNumber: int, shouldHydrateTransactions: bool = False) -> BlockData:
        response = await self._make_request(method='eth_getBlockByNumber', params=[hex(blockNumber), shouldHydrateTransactions])
        if response['result'] is None:
            raise NotFoundException()
        if self.isTestnet:
            # NOTE(krishan711): In testnet strip out the extra data as done by web3
            # https://web3py.readthedocs.io/en/stable/middleware.html#why-is-geth-poa-middleware-necessary
            response['result']['extraData'] = HexBytes('0').hex()
        return typing.cast(BlockData, method_formatters.PYTHONIC_RESULT_FORMATTERS[RPC.eth_getBlockByNumber](response['result']))

    async def get_block_uncle_count(self, blockNumber: int) -> int:
        response = await self._make_request(method='eth_getUncleCountByBlockNumber', params=[hex(blockNumber)])
        if response['result'] is None:
            raise NotFoundException()
        return typing.cast(int, method_formatters.PYTHONIC_RESULT_FORMATTERS[RPC.eth_getUncleCountByBlockNumber](response['result']))

    async def get_transaction_count(self, address: str) -> int:
        response = await self._make_request(method='eth_getTransactionCount', params=[address, 'latest'])
        if response['result'] is None:
            raise NotFoundException()
        return typing.cast(int, method_formatters.PYTHONIC_RESULT_FORMATTERS[RPC.eth_getTransactionCount](response['result']))

    async def get_transaction(self, transactionHash: str) -> TxData:
        response = await self._make_request(method='eth_getTransactionByHash', params=[transactionHash])
        if response['result'] is None:
            raise NotFoundException()
        return typing.cast(TxData, method_formatters.PYTHONIC_RESULT_FORMATTERS[RPC.eth_getTransactionByHash](response['result']))

    async def get_transaction_receipt(self, transactionHash: str) -> TxReceipt:
        response = await self._make_request(method='eth_getTransactionReceipt', params=[transactionHash])
        if response['result'] is None:
            raise NotFoundException()
        return typing.cast(TxReceipt, method_formatters.PYTHONIC_RESULT_FORMATTERS[RPC.eth_getTransactionReceipt](response['result']))

    async def get_log_entries(self, topics: Optional[List[str]] = None, startBlockNumber: Optional[int] = None, endBlockNumber: Optional[int] = None, address: Optional[str] = None) -> List[LogReceipt]:
        params: DictStrAny = {
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
        return typing.cast(List[LogReceipt], method_formatters.PYTHONIC_RESULT_FORMATTERS[RPC.eth_getLogs](response['result']))

    async def call_function(self, toAddress: str, contractAbi: ABI, functionAbi: ABIFunction, fromAddress: Optional[str] = None, arguments: Optional[DictStrAny] = None, blockNumber: Optional[int] = None) -> ListAny:
        data = encode_transaction_data(w3=self.w3, abi_element_identifier=functionAbi['name'], contract_abi=[functionAbi], abi_callable=functionAbi, kwargs=(arguments or {}), args=[])
        params = {
            'from': fromAddress or '0x0000000000000000000000000000000000000000',
            'to': toAddress,
            'data': data,
        }
        response = await self._make_request(method='eth_call', params=[params, blockNumber or 'latest'])
        outputTypes = get_abi_output_types(abi_element=functionAbi)
        try:
            outputData = self.w3.codec.decode(types=outputTypes, data=HexBytes(response['result']))
        except InsufficientDataBytes as exception:
            if response['result'] == '0x':
                raise BadRequestException(message=f'Empty response: {str(exception)}. Maybe the method does not exist on this contract.')
            raise exception
        except DecodingError as exception:
            raise BadRequestException(message=str(exception))
        return list(outputData)

    def _find_abi_by_name_args(self, contractAbi: ABI, functionName: str, arguments: Optional[DictStrAny] = None) -> ABIFunction:
        functionAbis = typing.cast(List[ABIFunction], [abi for abi in contractAbi if abi.get('name') == functionName])
        if len(functionAbis) == 0:
            raise BadRequestException(message='Function not found in ABI')
        if len(functionAbis) == 1:
            functionAbi = functionAbis[0]
        else:
            argumentCount = len(arguments or {})
            functionAbi = [abi for abi in functionAbis if len(abi['inputs']) == argumentCount][0]
        if not functionAbi:
            raise BadRequestException(message='Function not found in ABI')
        return functionAbi

    async def call_function_by_name(self, toAddress: str, contractAbi: ABI, functionName: str, fromAddress: Optional[str] = None, arguments: Optional[DictStrAny] = None, blockNumber: Optional[int] = None) -> ListAny:
        functionAbi = self._find_abi_by_name_args(contractAbi=contractAbi, functionName=functionName, arguments=arguments)
        return await self.call_function(toAddress=toAddress, contractAbi=contractAbi, functionAbi=functionAbi, fromAddress=fromAddress, arguments=arguments, blockNumber=blockNumber)

    def _get_base_transaction_params(self, toAddress: str, contractAbi: ABI, functionAbi: ABIFunction, fromAddress: str, arguments: Optional[DictStrAny] = None) -> DictStrAny:
        params = {
            'to': toAddress,
            'from': fromAddress,
            'data': encode_transaction_data(w3=self.w3, abi_element_identifier=functionAbi['name'], contract_abi=contractAbi, abi_callable=functionAbi, kwargs=(arguments or {}), args=[]),
        }
        return params

    async def _get_transaction_params(self, toAddress: str, contractAbi: ABI, functionAbi: ABIFunction, fromAddress: str, nonce: Optional[int] = None, gas: Optional[int] = None, maxFeePerGas: Optional[int] = None, maxPriorityFeePerGas: Optional[int] = None, arguments: Optional[DictStrAny] = None, chainId: Optional[int] = None) -> DictStrAny:
        params = self._get_base_transaction_params(toAddress=toAddress, contractAbi=contractAbi, functionAbi=functionAbi, fromAddress=fromAddress, arguments=arguments)
        if gas is None:
            response = await self._make_request(method='eth_estimateGas', params=[params])
            gas = int(response['result'], 16)
        params['gas'] = gas
        if maxPriorityFeePerGas is None:
            response = await self._make_request(method='eth_maxPriorityFeePerGas')
            maxPriorityFeePerGas = int(response['result'], 16)
        params['maxPriorityFeePerGas'] = maxPriorityFeePerGas
        if maxFeePerGas is None:
            response = await self._make_request(method='eth_getBlockByNumber', params=['pending', False])
            baseFeePerGas = int(response['result']['baseFeePerGas'], 16)
            maxFeePerGas = baseFeePerGas + maxPriorityFeePerGas
        params['maxFeePerGas'] = maxFeePerGas
        if nonce is None:
            nonce = await self.get_transaction_count(address=fromAddress)
        params['nonce'] = nonce
        if chainId is not None:
            params['chainId'] = chainId
        return params

    async def send_raw_transaction(self, transactionData: str) -> str:
        if not transactionData.startswith('0x'):
            transactionData = '0x' + transactionData
        response = await self._make_request(method='eth_sendRawTransaction', params=[transactionData])
        return typing.cast(str, response['result'])

    async def send_transaction(self, toAddress: str, contractAbi: ABI, functionAbi: ABIFunction, privateKey: str, fromAddress: str, nonce: Optional[int] = None, gas: Optional[int] = None, maxFeePerGas: Optional[int] = None, maxPriorityFeePerGas: Optional[int] = None, arguments: Optional[DictStrAny] = None, chainId: Optional[int] = None) -> str:
        params = await self._get_transaction_params(toAddress=toAddress, contractAbi=contractAbi, functionAbi=functionAbi, fromAddress=fromAddress, nonce=nonce, gas=gas, maxFeePerGas=maxFeePerGas, maxPriorityFeePerGas=maxPriorityFeePerGas, arguments=arguments, chainId=chainId)
        signedParams = self.w3.eth.account.sign_transaction(transaction_dict=params, private_key=privateKey)
        output = await self.send_raw_transaction(transactionData=signedParams.raw_transaction.hex())
        return output

    async def send_transaction_by_name(self, toAddress: str, contractAbi: ABI, functionName: str, privateKey: str, fromAddress: str, nonce: Optional[int] = None, gas: Optional[int] = None, maxFeePerGas: Optional[int] = None, maxPriorityFeePerGas: Optional[int] = None, arguments: Optional[DictStrAny] = None, chainId: Optional[int] = None) -> str:
        functionAbi = self._find_abi_by_name_args(contractAbi=contractAbi, functionName=functionName, arguments=arguments)
        return await self.send_transaction(toAddress=toAddress, contractAbi=contractAbi, functionAbi=functionAbi, privateKey=privateKey, fromAddress=fromAddress, nonce=nonce, gas=gas, maxFeePerGas=maxFeePerGas, maxPriorityFeePerGas=maxPriorityFeePerGas, arguments=arguments, chainId=chainId)

    async def wait_for_transaction_receipt(self, transactionHash: str, sleepSeconds: int = 2) -> TxReceipt:
        while True:
            try:
                transactionReceipt = await self.get_transaction_receipt(transactionHash=transactionHash)
                return transactionReceipt
            except NotFoundException:
                pass
            await asyncio.sleep(sleepSeconds)
