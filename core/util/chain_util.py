import typing

import eth_utils
from eth_typing import ABIComponent
from eth_typing import ABIFunction
from eth_typing import HexStr
from eth_utils import add_0x_prefix
from eth_utils import keccak
from web3 import Web3
from web3._utils.contracts import encode_abi
from web3._utils.contracts import encode_transaction_data as web3_encode_transaction_data
from web3.types import ChecksumAddress

BURN_ADDRESS = '0x0000000000000000000000000000000000000000'


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
    w3: Web3,
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
        w3=w3,
        abi_element_identifier=functionAbi['name'],
        contract_abi=[functionAbi],
        abi_callable=functionAbi,
        kwargs=arguments or {},
        args=[],
    )


def encode_function_params(functionAbi: ABIFunction, arguments: list[typing.Any]) -> str:  # type: ignore[explicit-any]
    return add_0x_prefix(
        encode_abi(
            w3=Web3(),
            abi=functionAbi,
            arguments=arguments,
        )
    )


def _get_canonical_type(param: ABIComponent) -> str:
    paramType = param['type']
    if paramType == 'tuple' and 'components' in param:
        componentTypes = [_get_canonical_type(component) for component in param['components']]
        return f'({",".join(componentTypes)})'
    if paramType == 'tuple[]' and 'components' in param:
        componentTypes = [_get_canonical_type(component) for component in param['components']]
        return f'({",".join(componentTypes)})[]'
    return paramType


# NOTE(krishan711): is this the exact same thing as encode_transaction_data??
def encode_function_call(functionAbi: ABIFunction, arguments: list[typing.Any]) -> str:  # type: ignore[explicit-any]
    functionName = functionAbi['name']
    paramTypes = [_get_canonical_type(param=param) for param in functionAbi['inputs']]
    signatureString = f'{functionName}({",".join(paramTypes)})'
    keccakHash = keccak(text=signatureString).hex()
    signature = '0x' + keccakHash[:8]
    encodedParams = encode_function_params(functionAbi=functionAbi, arguments=arguments)
    return signature + encodedParams[2:] if encodedParams.startswith('0x') else signature + encodedParams
