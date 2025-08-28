import typing

import eth_utils
from eth_abi.exceptions import DecodingError
from eth_typing import ABI
from eth_typing import ABIFunction
from eth_typing import HexStr
from eth_utils import add_0x_prefix
from eth_utils.abi import get_abi_output_types
from web3 import Web3
from web3._utils.contracts import encode_abi as web3_encode_abi
from web3._utils.contracts import encode_transaction_data as web3_encode_transaction_data
from web3.types import ChecksumAddress

from core.exceptions import BadRequestException

DictStrAny = dict[str, typing.Any]  # type: ignore[explicit-any]

BURN_ADDRESS = '0x0000000000000000000000000000000000000000'
_w3 = Web3()


def normalize_address(value: str) -> str:
    return str(normalize_address_checksum(value=value))


def normalize_address_checksum(value: str) -> ChecksumAddress:
    addressBytes = eth_utils.to_bytes(hexstr=value)
    return Web3.to_checksum_address(addressBytes[-20:])


def _convert_parameter_value(abiInput: typing.Any, value: typing.Any) -> typing.Any:  # type: ignore[explicit-any]
    paramType = abiInput['type']
    if paramType == 'tuple' and 'components' in abiInput:
        return _convert_tuple_parameter_values(abiInputs=abiInput['components'], argumentValues=value)
    # Handle uint types (uint8, uint16, uint32, uint64, ..., int8, int16, int32, ...)
    if paramType.startswith(('uint', 'int')) and isinstance(value, str) and value.startswith('0x'):
        try:
            return int(value, 16)
        except ValueError:
            return value
    # NOTE(krishan711): tuples will be handlded by a separate function
    return value


def _convert_tuple_parameter_values(abiInputs: list[typing.Any], argumentValues: typing.Any) -> typing.Any:  # type: ignore[explicit-any]
    if isinstance(argumentValues, dict):
        convertedMap = {}
        for abiInput in abiInputs:
            paramName = abiInput['name']
            if paramName in argumentValues:
                convertedMap[paramName] = _convert_parameter_value(abiInput=abiInput, value=argumentValues[paramName])
        return convertedMap
    if isinstance(argumentValues, list | tuple):
        convertedList = []
        for i, abiInput in enumerate(abiInputs):
            if i < len(argumentValues):
                convertedList.append(_convert_parameter_value(abiInput=abiInput, value=argumentValues[i]))
        return convertedList if isinstance(argumentValues, list) else tuple(convertedList)
    return argumentValues


def encode_transaction_data(  # type: ignore[explicit-any]
    functionAbi: ABIFunction,
    arguments: dict[str, typing.Any] | None = None,
) -> HexStr:
    # NOTE(krishan711): web3py doesn't like hex strings for ints but coinbase rpc expects it :(
    if arguments is not None:
        for abiInput in functionAbi['inputs']:
            paramName = abiInput['name']
            if paramName in arguments:
                arguments[paramName] = _convert_parameter_value(abiInput=abiInput, value=arguments[paramName])
    return web3_encode_transaction_data(
        w3=_w3,
        abi_element_identifier=functionAbi['name'],
        contract_abi=[functionAbi],
        abi_callable=functionAbi,
        kwargs=arguments or {},
        args=[],
    )


def find_abi_by_name_args(contractAbi: ABI, functionName: str, arguments: DictStrAny | None = None) -> ABIFunction:
    functionAbis = typing.cast(list[ABIFunction], [abi for abi in contractAbi if abi.get('name') == functionName])
    if len(functionAbis) == 0:
        raise BadRequestException(message='Function not found in ABI')
    functionAbi: ABIFunction | None = None
    if len(functionAbis) == 1:
        functionAbi = functionAbis[0]
    else:
        argumentCount = len(arguments or {})
        functionAbi = next((abi for abi in functionAbis if len(abi['inputs']) == argumentCount), None)
    if not functionAbi:
        raise BadRequestException(message='Function not found in ABI')
    return functionAbi


def encode_transaction_data_by_name(  # type: ignore[explicit-any]
    contractAbi: ABI,
    functionName: str,
    arguments: dict[str, typing.Any] | None = None,
) -> HexStr:
    # NOTE(krishan711): web3py doesn't like hex strings for ints but coinbase rpc expects it :(
    functionAbi = _w3.eth.contract(abi=contractAbi).get_function_by_name(functionName).abi
    if arguments is not None:
        for abiInput in functionAbi['inputs']:
            paramName = abiInput['name']
            if paramName in arguments:
                arguments[paramName] = _convert_parameter_value(abiInput=abiInput, value=arguments[paramName])
    return web3_encode_transaction_data(
        w3=_w3,
        abi_element_identifier=functionAbi['name'],
        contract_abi=[functionAbi],
        abi_callable=functionAbi,
        kwargs=arguments or {},
        args=[],
    )


# NOTE(krishan711): not sure how different this is from `encode_transaction_data`
def encode_function_params(functionAbi: ABIFunction, arguments: list[typing.Any]) -> str:  # type: ignore[explicit-any]
    return add_0x_prefix(
        web3_encode_abi(
            w3=_w3,
            abi=functionAbi,
            arguments=arguments,
        )
    )


def decode_function_result(functionAbi: ABIFunction, resultData: bytes) -> list[typing.Any]:  # type: ignore[explicit-any]
    if resultData == b'' or resultData.hex() == '0x':
        outputs = functionAbi.get('outputs', [])
        if len(outputs) == 0:
            return []
        raise BadRequestException(message=f'Empty response. Maybe the method does not exist on this contract.')
    outputTypes = get_abi_output_types(abi_element=functionAbi)
    try:
        outputData = _w3.codec.decode(types=outputTypes, data=bytes.fromhex(resultData.hex()))
    except DecodingError as exception:
        raise BadRequestException(message=str(exception))
    return list(outputData)
