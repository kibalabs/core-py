import asyncio
import typing
from typing import Any

from eth_typing import ABI
from eth_typing import ABIFunction
from pydantic import BaseModel
from web3 import Web3
from web3._utils import method_formatters
from web3._utils.rpc_abi import RPC
from web3.types import BlockData
from web3.types import HexBytes
from web3.types import HexStr
from web3.types import LogReceipt
from web3.types import TxData
from web3.types import TxParams
from web3.types import TxReceipt
from web3.types import Wei

from core import logging
from core.exceptions import BadRequestException
from core.exceptions import ClientException
from core.exceptions import KibaException
from core.exceptions import NotFoundException
from core.exceptions import TooManyRequestsException
from core.requester import Requester
from core.util import chain_util
from core.util import json_util
from core.util.typing_util import JsonObject
from core.web3.multicall3 import CHAIN_ID_MULTICALL3_ADDRESS_MAP
from core.web3.multicall3 import MULTICALL3_ABI

ListAny = list[Any]  # type: ignore[explicit-any]
DictStrAny = dict[str, Any]  # type: ignore[explicit-any]


class EncodedCall(BaseModel):
    toAddress: str
    value: int = 0
    data: str = '0x'


class ContractCall(BaseModel):
    toAddress: str
    functionName: str
    contractAbi: ABI
    arguments: DictStrAny | None = None
    fromAddress: str | None = None


class TransactionFailedException(KibaException):
    def __init__(self, transactionReceipt: TxReceipt) -> None:
        super().__init__(message='Transaction failed')
        self.transactionReceipt = transactionReceipt

    def to_dict(self) -> JsonObject:
        output = super().to_dict()
        typing.cast(JsonObject, output['fields'])['transactionReceipt'] = json_util.loads(json_util.dumps(self.transactionReceipt))
        return output


class EthClientInterface:
    def __init__(self, web3Connection: Web3, chainId: int, isTestnet: bool = False) -> None:
        self.w3 = web3Connection
        self.chainId = chainId
        self.isTestnet = isTestnet

    async def get_latest_block_number(self) -> int:
        raise NotImplementedError

    async def get_block(self, blockNumber: int, shouldHydrateTransactions: bool = False) -> BlockData:
        raise NotImplementedError

    async def get_block_uncle_count(self, blockNumber: int) -> int:
        raise NotImplementedError

    async def get_transaction(self, transactionHash: str) -> TxData:
        raise NotImplementedError

    async def get_transaction_receipt(self, transactionHash: str) -> TxReceipt:
        raise NotImplementedError

    async def get_log_entries(self, topics: list[str] | None = None, startBlockNumber: int | None = None, endBlockNumber: int | None = None, address: str | None = None) -> list[LogReceipt]:
        raise NotImplementedError

    async def call(self, contractCall: ContractCall, blockNumber: int | None = None) -> ListAny:
        raise NotImplementedError

    async def fill_transaction_params(
        self,
        params: TxParams,
        fromAddress: str,
        nonce: int | None = None,
        gas: int | None = None,
        maxFeePerGas: int | None = None,
        maxPriorityFeePerGas: int | None = None,
        chainId: int | None = None,
    ) -> TxParams:
        raise NotImplementedError

    async def send_raw_transaction(self, transactionData: str) -> str:
        raise NotImplementedError

    async def call_function_by_name(
        self,
        toAddress: str,
        contractAbi: ABI,
        functionName: str,
        fromAddress: str | None = None,
        arguments: DictStrAny | None = None,
        blockNumber: int | None = None,
    ) -> ListAny:
        return await self.call(
            contractCall=ContractCall(
                toAddress=toAddress,
                functionName=functionName,
                contractAbi=contractAbi,
                arguments=arguments,
                fromAddress=fromAddress,
            ),
            blockNumber=blockNumber,
        )

    async def call_function(
        self,
        toAddress: str,
        contractAbi: ABI,
        functionAbi: ABIFunction,
        fromAddress: str | None = None,
        arguments: DictStrAny | None = None,
        blockNumber: int | None = None,
    ) -> ListAny:
        return await self.call(
            contractCall=ContractCall(
                toAddress=toAddress,
                functionName=functionAbi['name'],
                contractAbi=contractAbi,
                arguments=arguments,
                fromAddress=fromAddress,
            ),
            blockNumber=blockNumber,
        )

    async def send_transaction(
        self,
        toAddress: str,
        # TODO(krishan711): remove on major bump
        contractAbi: ABI,  # noqa: ARG002
        functionAbi: ABIFunction,
        privateKey: str,
        fromAddress: str,
        nonce: int | None = None,
        gas: int | None = None,
        maxFeePerGas: int | None = None,
        maxPriorityFeePerGas: int | None = None,
        arguments: DictStrAny | None = None,
        chainId: int | None = None,
    ) -> str:
        params: TxParams = {
            'to': chain_util.normalize_address(value=toAddress),
            'from': chain_util.normalize_address(value=fromAddress),
            'data': chain_util.encode_transaction_data(functionAbi=functionAbi, arguments=arguments),
        }
        params = await self.fill_transaction_params(
            params=params,
            fromAddress=fromAddress,
            nonce=nonce,
            gas=gas,
            maxFeePerGas=maxFeePerGas,
            maxPriorityFeePerGas=maxPriorityFeePerGas,
            chainId=chainId or self.chainId,
        )
        signedParams = self.w3.eth.account.sign_transaction(transaction_dict=params, private_key=privateKey)
        output = await self.send_raw_transaction(transactionData=signedParams.raw_transaction.hex())
        return output

    async def send_transaction_by_name(
        self,
        toAddress: str,
        contractAbi: ABI,
        functionName: str,
        privateKey: str,
        fromAddress: str,
        nonce: int | None = None,
        gas: int | None = None,
        maxFeePerGas: int | None = None,
        maxPriorityFeePerGas: int | None = None,
        arguments: DictStrAny | None = None,
        chainId: int | None = None,
    ) -> str:
        functionAbi = chain_util.find_abi_by_name_args(contractAbi=contractAbi, functionName=functionName, arguments=arguments)
        return await self.send_transaction(
            toAddress=toAddress,
            contractAbi=contractAbi,
            functionAbi=functionAbi,
            privateKey=privateKey,
            fromAddress=fromAddress,
            nonce=nonce,
            gas=gas,
            maxFeePerGas=maxFeePerGas,
            maxPriorityFeePerGas=maxPriorityFeePerGas,
            arguments=arguments,
            chainId=chainId or self.chainId,
        )

    async def wait_for_transaction_receipt(self, transactionHash: str, sleepSeconds: int = 2, maxWaitSeconds: int = 120, raiseOnFailure: bool = True) -> TxReceipt:
        startTime = asyncio.get_event_loop().time()
        while True:
            try:
                transactionReceipt = await self.get_transaction_receipt(transactionHash=transactionHash)
            except NotFoundException:
                pass
            else:
                break
            currentTime = asyncio.get_event_loop().time()
            if currentTime - startTime >= maxWaitSeconds:
                raise TimeoutError(f'Transaction receipt not found after {maxWaitSeconds} seconds')
            await asyncio.sleep(sleepSeconds)
        if raiseOnFailure and transactionReceipt['status'] == 0:
            raise TransactionFailedException(transactionReceipt=transactionReceipt)
        return transactionReceipt

    async def multicall(self, contractCalls: list[ContractCall], shouldUseMulticall3: bool = True) -> list[ListAny]:
        multicall3Address = CHAIN_ID_MULTICALL3_ADDRESS_MAP.get(self.chainId) if shouldUseMulticall3 else None
        if not multicall3Address or not shouldUseMulticall3:
            results = await asyncio.gather(*[self.call(contractCall=contractCall) for contractCall in contractCalls])
            return results
        multicallResponse = await self.call_function_by_name(
            toAddress=multicall3Address,
            contractAbi=MULTICALL3_ABI,
            functionName='aggregate3',
            arguments={
                'calls': [
                    {'target': contractCall.toAddress, 'allowFailure': False, 'callData': chain_util.encode_transaction_data_by_name(contractAbi=contractCall.contractAbi, functionName=contractCall.functionName, arguments=contractCall.arguments)}
                    for contractCall in contractCalls
                ]
            },
        )
        multicallResults = multicallResponse[0]
        decodedResults: list[ListAny] = []
        for contractCall, (success, returnData) in zip(contractCalls, multicallResults, strict=False):
            if not success:
                decodedResults.append([None])
                continue
            functionAbi = chain_util.find_abi_by_name_args(contractAbi=contractCall.contractAbi, functionName=contractCall.functionName, arguments=contractCall.arguments)
            decodedValue = chain_util.decode_function_result(functionAbi=functionAbi, resultData=returnData)
            decodedResults.append(decodedValue)
        return decodedResults


class Web3EthClient(EthClientInterface):
    def __init__(self, web3Connection: Web3, chainId: int, isTestnet: bool = False) -> None:
        super().__init__(web3Connection=web3Connection, chainId=chainId, isTestnet=isTestnet)

    async def get_latest_block_number(self) -> int:
        return self.w3.eth.block_number

    async def get_block(self, blockNumber: int, shouldHydrateTransactions: bool = False) -> BlockData:
        return self.w3.eth.get_block(blockNumber, shouldHydrateTransactions)

    async def get_block_uncle_count(self, blockNumber: int) -> int:
        return typing.cast(int, self.w3.eth.get_uncle_count(blockNumber))

    async def get_transaction_count(self, address: str) -> int:
        return self.w3.eth.get_transaction_count(chain_util.normalize_address_checksum(value=address))

    async def get_transaction(self, transactionHash: str) -> TxData:
        return self.w3.eth.get_transaction(typing.cast(HexStr, transactionHash))

    async def get_transaction_receipt(self, transactionHash: str) -> TxReceipt:
        return self.w3.eth.get_transaction_receipt(typing.cast(HexStr, transactionHash))

    async def get_log_entries(
        self,
        topics: list[str] | None = None,
        startBlockNumber: int | None = None,
        endBlockNumber: int | None = None,
        address: str | None = None,
    ) -> list[LogReceipt]:
        contractFilter = self.w3.eth.filter(
            {
                'fromBlock': startBlockNumber,  # type: ignore[typeddict-item]
                'toBlock': endBlockNumber,  # type: ignore[typeddict-item]
                'topics': topics,  # type: ignore[typeddict-item]
                'address': address,  # type: ignore[typeddict-item]
            }
        )
        return contractFilter.get_all_entries()


class RestEthClient(EthClientInterface):
    # NOTE(krishan711): find docs at https://eth.wiki/json-rpc/API
    def __init__(self, url: str, requester: Requester, chainId: int, isTestnet: bool = False, shouldBackoffRetryOnRateLimit: bool = True, retryLimit: int = 10) -> None:
        super().__init__(web3Connection=Web3(), chainId=chainId, isTestnet=isTestnet)
        self.url = url
        self.requester = requester
        self.shouldBackoffRetryOnRateLimit = shouldBackoffRetryOnRateLimit
        self.retryLimit = retryLimit
        self.w3 = Web3()

    @staticmethod
    def _hex_to_int(value: str) -> int:
        return int(value, 16)

    async def _make_request(self, method: str, params: ListAny | None = None) -> DictStrAny:
        retryCount = 0
        initialBackoffSeconds = 1.0
        responseDict: DictStrAny = {}
        while True:
            try:
                response = await self.requester.post_json(
                    url=self.url,
                    dataDict={'jsonrpc': '2.0', 'method': method, 'params': params or [], 'id': None},
                    timeout=10,
                )
                responseDict = response.json()
                if responseDict.get('error'):
                    errorMessage = responseDict['error'].get('message') or responseDict['error'].get('details') or json_util.dumps(responseDict['error'])
                    raise BadRequestException(message=errorMessage)
            except ClientException as exception:
                # NOTE(krishan711): this is just here to debug 429s from coinbase, remove when done
                logging.info(f'caught exception on _make_request: {exception!s}')
                exceptionMessage = exception.message or ''
                if (
                    isinstance(exception, TooManyRequestsException)
                    # NOTE(krishan711): sometimes coinbase returns an error message with 200 status
                    or 'over rate limit' in exceptionMessage
                    or '429 Too Many Requests' in exceptionMessage
                ):
                    if not self.shouldBackoffRetryOnRateLimit or retryCount >= self.retryLimit:
                        raise
                    retryCount += 1
                    exponentialBackoffSeconds = initialBackoffSeconds * (2 ** (retryCount - 1))
                    logging.info(f'Retrying {method} after {exponentialBackoffSeconds} seconds due to rate limit exceeded: {exception!s}')
                    await asyncio.sleep(exponentialBackoffSeconds)
                    continue
                raise
            return responseDict

    async def get_latest_block_number(self) -> int:
        response = await self._make_request(method='eth_blockNumber')
        if response['result'] is None:
            raise NotFoundException
        return typing.cast(int, method_formatters.PYTHONIC_RESULT_FORMATTERS[RPC.eth_blockNumber](response['result']))

    async def get_latest_block(self, shouldHydrateTransactions: bool = False) -> BlockData:
        response = await self._make_request(method='eth_getBlockByNumber', params=['latest', shouldHydrateTransactions])
        if response['result'] is None:
            raise NotFoundException
        if self.isTestnet:
            # NOTE(krishan711): In testnet strip out the extra data as done by web3
            # https://web3py.readthedocs.io/en/stable/middleware.html#why-is-geth-poa-middleware-necessary
            response['result']['extraData'] = HexBytes('0').hex()
        return typing.cast(BlockData, method_formatters.PYTHONIC_RESULT_FORMATTERS[RPC.eth_getBlockByNumber](response['result']))

    async def get_block(self, blockNumber: int, shouldHydrateTransactions: bool = False) -> BlockData:
        response = await self._make_request(method='eth_getBlockByNumber', params=[hex(blockNumber), shouldHydrateTransactions])
        if response['result'] is None:
            raise NotFoundException
        if self.isTestnet:
            # NOTE(krishan711): In testnet strip out the extra data as done by web3
            # https://web3py.readthedocs.io/en/stable/middleware.html#why-is-geth-poa-middleware-necessary
            response['result']['extraData'] = HexBytes('0').hex()
        return typing.cast(BlockData, method_formatters.PYTHONIC_RESULT_FORMATTERS[RPC.eth_getBlockByNumber](response['result']))

    async def get_block_uncle_count(self, blockNumber: int) -> int:
        response = await self._make_request(method='eth_getUncleCountByBlockNumber', params=[hex(blockNumber)])
        if response['result'] is None:
            raise NotFoundException
        return typing.cast(int, method_formatters.PYTHONIC_RESULT_FORMATTERS[RPC.eth_getUncleCountByBlockNumber](response['result']))

    async def get_transaction_count(self, address: str) -> int:
        response = await self._make_request(method='eth_getTransactionCount', params=[address, 'latest'])
        if response['result'] is None:
            raise NotFoundException
        return typing.cast(int, method_formatters.PYTHONIC_RESULT_FORMATTERS[RPC.eth_getTransactionCount](response['result']))

    async def get_transaction(self, transactionHash: str) -> TxData:
        response = await self._make_request(method='eth_getTransactionByHash', params=[transactionHash])
        if response['result'] is None:
            raise NotFoundException
        return typing.cast(TxData, method_formatters.PYTHONIC_RESULT_FORMATTERS[RPC.eth_getTransactionByHash](response['result']))

    async def get_transaction_receipt(self, transactionHash: str) -> TxReceipt:
        response = await self._make_request(method='eth_getTransactionReceipt', params=[transactionHash])
        if response['result'] is None:
            raise NotFoundException
        return typing.cast(TxReceipt, method_formatters.PYTHONIC_RESULT_FORMATTERS[RPC.eth_getTransactionReceipt](response['result']))

    async def get_log_entries(
        self,
        topics: list[str] | None = None,
        startBlockNumber: int | None = None,
        endBlockNumber: int | None = None,
        address: str | None = None,
    ) -> list[LogReceipt]:
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
        return typing.cast(list[LogReceipt], method_formatters.PYTHONIC_RESULT_FORMATTERS[RPC.eth_getLogs](response['result']))

    async def call(
        self,
        contractCall: ContractCall,
        blockNumber: int | None = None,
    ) -> ListAny:
        params = {
            'from': contractCall.fromAddress or '0x0000000000000000000000000000000000000000',
            'to': contractCall.toAddress,
            'data': chain_util.encode_transaction_data_by_name(contractAbi=contractCall.contractAbi, functionName=contractCall.functionName, arguments=contractCall.arguments),
        }
        functionAbi = chain_util.find_abi_by_name_args(contractAbi=contractCall.contractAbi, functionName=contractCall.functionName, arguments=contractCall.arguments)
        response = await self._make_request(method='eth_call', params=[params, hex(blockNumber) if blockNumber is not None else 'latest'])
        decodedResponse = chain_util.decode_function_result(functionAbi=functionAbi, resultData=HexBytes(response['result']))
        return decodedResponse

    async def get_max_priority_fee_per_gas(self) -> int:
        response = await self._make_request(method='eth_maxPriorityFeePerGas')
        maxPriorityFeePerGas = int(response['result'], 16)
        return maxPriorityFeePerGas

    async def get_max_fee_per_gas(self, maxPriorityFeePerGas: int | str) -> int:
        response = await self._make_request(method='eth_getBlockByNumber', params=['pending', False])
        baseFeePerGas = int(response['result']['baseFeePerGas'], 16)
        intMaxPriorityFeePerGas: int = typing.cast(Wei, int(maxPriorityFeePerGas, 16)) if isinstance(maxPriorityFeePerGas, str) else maxPriorityFeePerGas
        maxFeePerGas = baseFeePerGas + intMaxPriorityFeePerGas
        return maxFeePerGas

    async def fill_transaction_params(
        self,
        params: TxParams,
        fromAddress: str,
        nonce: int | None = None,
        gas: int | None = None,
        maxFeePerGas: int | None = None,
        maxPriorityFeePerGas: int | None = None,
        chainId: int | None = None,
    ) -> TxParams:
        if 'chainId' not in params:
            if chainId is None:
                chainId = self.chainId
            params['chainId'] = hex(chainId)  # type: ignore[typeddict-item]
        if 'nonce' not in params:
            if nonce is None:
                nonce = await self.get_transaction_count(address=fromAddress)
            params['nonce'] = hex(nonce)  # type: ignore[typeddict-item]
        if 'gas' not in params:
            if gas is None:
                response = await self._make_request(method='eth_estimateGas', params=[params])
                gas = int(response['result'], 16)
            params['gas'] = hex(gas)  # type: ignore[typeddict-item]
        if 'gasPrice' not in params:
            if 'maxPriorityFeePerGas' not in params:
                if maxPriorityFeePerGas is None:
                    maxPriorityFeePerGas = await self.get_max_priority_fee_per_gas()
                params['maxPriorityFeePerGas'] = hex(maxPriorityFeePerGas)
            if 'maxFeePerGas' not in params:
                if maxFeePerGas is None:
                    maxFeePerGas = await self.get_max_fee_per_gas(maxPriorityFeePerGas=params['maxPriorityFeePerGas'])
                params['maxFeePerGas'] = hex(maxFeePerGas)
        return params

    async def send_raw_transaction(self, transactionData: str) -> str:
        if not transactionData.startswith('0x'):
            transactionData = '0x' + transactionData
        response = await self._make_request(method='eth_sendRawTransaction', params=[transactionData])
        return typing.cast(str, response['result'])
