import pytest
from web3 import Web3
from eth_typing import ABIFunction

from core.util import chain_util


class TestChainUtil:

    def test_normalize_address_with_lowercase_address(self):
        address = "0xa0b86a33e6351ccede6dea8975b5e3fb6e6d9d1e"
        result = chain_util.normalize_address(value=address)
        assert result == "0xA0B86a33E6351CcEDE6DEa8975b5e3FB6E6d9d1e"

    def test_normalize_address_with_uppercase_address(self):
        address = "0xA0B86A33E6351CCEDE6DEA8975B5E3FB6E6D9D1E"
        result = chain_util.normalize_address(value=address)
        assert result == "0xA0B86a33E6351CcEDE6DEa8975b5e3FB6E6d9d1e"

    def test_normalize_address_with_mixed_case_address(self):
        address = "0xa0B86a33E6351CcedE6dEa8975b5E3FB6e6d9d1E"
        result = chain_util.normalize_address(value=address)
        assert result == "0xA0B86a33E6351CcEDE6DEa8975b5e3FB6E6d9d1e"

    def test_normalize_address_with_short_address(self):
        address = "0x1234"
        with pytest.raises(ValueError):
            chain_util.normalize_address(value=address)

    def test_normalize_address_checksum_returns_checksum_address(self):
        address = "0xa0b86a33e6351ccede6dea8975b5e3fb6e6d9d1e"
        result = chain_util.normalize_address_checksum(value=address)
        assert result == "0xA0B86a33E6351CcEDE6DEa8975b5e3FB6E6d9d1e"
        assert Web3.is_checksum_address(result)

    def test_encode_transaction_data_with_simple_function(self):
        w3 = Web3()
        function_abi = {
            'inputs': [{'name': 'amount', 'type': 'uint256'}],
            'name': 'transfer',
            'outputs': [],
            'stateMutability': 'nonpayable',
            'type': 'function'
        }
        arguments = {'amount': 1000}
        result = chain_util.encode_transaction_data(w3=w3, functionAbi=function_abi, arguments=arguments)
        assert result.startswith('0x')
        assert len(result) > 10

    def test_encode_transaction_data_with_hex_arguments(self):
        w3 = Web3()
        function_abi = {
            'inputs': [{'name': 'amount', 'type': 'uint256'}],
            'name': 'transfer',
            'outputs': [],
            'stateMutability': 'nonpayable',
            'type': 'function'
        }
        arguments = {'amount': '0x3e8'}
        result = chain_util.encode_transaction_data(w3=w3, functionAbi=function_abi, arguments=arguments)
        assert result.startswith('0x')
        assert len(result) > 10

    def test_encode_transaction_data_with_no_arguments(self):
        w3 = Web3()
        function_abi = {
            'inputs': [],
            'name': 'getValue',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'stateMutability': 'view',
            'type': 'function'
        }
        result = chain_util.encode_transaction_data(w3=w3, functionAbi=function_abi, arguments=None)
        assert result.startswith('0x')
        assert len(result) == 10

    def test_encode_function_params_with_single_uint256(self):
        function_abi = {
            'inputs': [{'name': 'amount', 'type': 'uint256'}],
            'name': 'transfer',
            'outputs': [],
            'stateMutability': 'nonpayable',
            'type': 'function'
        }
        result = chain_util.encode_function_params(functionAbi=function_abi, arguments=[1000])
        assert result.startswith('0x')
        assert len(result) == 66

    def test_encode_function_params_with_multiple_parameters(self):
        function_abi = {
            'inputs': [
                {'name': 'to', 'type': 'address'},
                {'name': 'amount', 'type': 'uint256'}
            ],
            'name': 'transfer',
            'outputs': [],
            'stateMutability': 'nonpayable',
            'type': 'function'
        }
        result = chain_util.encode_function_params(
            functionAbi=function_abi,
            arguments=['0xA0B86a33E6351CcEDE6DEa8975b5e3FB6E6d9d1e', 1000]
        )
        assert result.startswith('0x')
        assert len(result) == 130

    def test_encode_function_params_with_no_parameters(self):
        function_abi = {
            'inputs': [],
            'name': 'getValue',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'stateMutability': 'view',
            'type': 'function'
        }
        result = chain_util.encode_function_params(functionAbi=function_abi, arguments=[])
        assert result == '0x'

    def test_encode_function_call_with_single_parameter(self):
        function_abi = {
            'inputs': [{'name': 'a', 'type': 'uint256'}],
            'name': 'bar',
            'outputs': [],
            'stateMutability': 'nonpayable',
            'type': 'function'
        }
        result = chain_util.encode_function_call(functionAbi=function_abi, arguments=[1])
        expected = '0x0423a1320000000000000000000000000000000000000000000000000000000000000001'
        assert result == expected

    def test_encode_function_call_with_no_parameters(self):
        function_abi = {
            'inputs': [],
            'name': 'foo',
            'outputs': [],
            'stateMutability': 'nonpayable',
            'type': 'function'
        }
        result = chain_util.encode_function_call(functionAbi=function_abi, arguments=[])
        expected = '0xc2985578'
        assert result == expected

    def test_encode_function_call_with_multiple_parameters(self):
        function_abi = {
            'inputs': [
                {'name': 'a', 'type': 'uint256'},
                {'name': 'b', 'type': 'address'}
            ],
            'name': 'multiParam',
            'outputs': [],
            'stateMutability': 'nonpayable',
            'type': 'function'
        }
        result = chain_util.encode_function_call(
            functionAbi=function_abi,
            arguments=[42, '0xA0B86a33E6351CcEDE6DEa8975b5e3FB6E6d9d1e']
        )
        assert result == '0x5b186084000000000000000000000000000000000000000000000000000000000000002a000000000000000000000000a0b86a33e6351ccede6dea8975b5e3fb6e6d9d1e'

    def test_encode_function_call_with_string_parameter(self):
        function_abi = {
            'inputs': [{'name': 'message', 'type': 'string'}],
            'name': 'setMessage',
            'outputs': [],
            'stateMutability': 'nonpayable',
            'type': 'function'
        }
        result = chain_util.encode_function_call(functionAbi=function_abi, arguments=['hello'])
        assert result == '0x368b87720000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000000568656c6c6f000000000000000000000000000000000000000000000000000000'

    def test_encode_function_call_signature_generation(self):
        function_abi = {
            'inputs': [
                {'name': 'a', 'type': 'uint256'},
                {'name': 'b', 'type': 'bool'},
                {'name': 'c', 'type': 'string'}
            ],
            'name': 'complexFunction',
            'outputs': [],
            'stateMutability': 'nonpayable',
            'type': 'function'
        }
        result = chain_util.encode_function_call(functionAbi=function_abi, arguments=[1, True, 'test'])
        assert result == '0x3d3d8f0a00000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000006000000000000000000000000000000000000000000000000000000000000000047465737400000000000000000000000000000000000000000000000000000000'

    def test_encode_function_call_with_tuple(self):
        function_abi = {
          'inputs': [
            {
              'components': [
                {'name': 'weight', 'type': 'uint256'},
                {'name': 'voted', 'type': 'bool'},
                {'name': 'delegate', 'type': 'address'},
                {'name': 'vote', 'type': 'uint256'},
              ],
              'name': 'voter',
              'type': 'tuple',
            },
          ],
          'name': 'getVoter',
          'outputs': [],
          'stateMutability': 'nonpayable',
          'type': 'function',
        }
        result = chain_util.encode_function_call(functionAbi=function_abi, arguments=[(69420, True, '0xa5cc3c03994DB5b0d9A5eEdD10CabaB0813678AC', 41)])
        assert result == '0xf37414670000000000000000000000000000000000000000000000000000000000010f2c0000000000000000000000000000000000000000000000000000000000000001000000000000000000000000a5cc3c03994db5b0d9a5eedd10cabab0813678ac0000000000000000000000000000000000000000000000000000000000000029'

    def test_encode_function_call_with_tuple_array(self):
        # 0x34fcd5be
        function_abi = {
        'inputs': [
                {
                    'components': [
                        {'name': 'target', 'type': 'address'},
                        {'name': 'value', 'type': 'uint256'},
                        {'name': 'data', 'type': 'bytes'},
                    ],
                    'internalType': 'struct CoinbaseSmartWallet.Call[]',
                    'name': 'calls',
                    'type': 'tuple[]',
                }
            ],
            'name': 'executeBatch',
            'outputs': [],
            'stateMutability': 'payable',
            'type': 'function',
        }
        result = chain_util.encode_function_call(functionAbi=function_abi, arguments=[[('0xa5cc3c03994DB5b0d9A5eEdD10CabaB0813678AC', 123, '0x1234567890abcdef')]])
        assert result == '0x34fcd5be000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000020000000000000000000000000a5cc3c03994db5b0d9a5eedd10cabab0813678ac000000000000000000000000000000000000000000000000000000000000007b000000000000000000000000000000000000000000000000000000000000006000000000000000000000000000000000000000000000000000000000000000081234567890abcdef000000000000000000000000000000000000000000000000'

    def test_encode_transaction_data_with_tuple_array(self):
        w3 = Web3()
        function_abi = {
            'inputs': [
                {
                    'components': [
                        {'name': 'target', 'type': 'address'},
                        {'name': 'value', 'type': 'uint256'},
                        {'name': 'data', 'type': 'bytes'},
                    ],
                    'internalType': 'struct CoinbaseSmartWallet.Call[]',
                    'name': 'calls',
                    'type': 'tuple[]',
                }
            ],
            'name': 'executeBatch',
            'outputs': [],
            'stateMutability': 'payable',
            'type': 'function',
        }
        arguments = {'calls': [('0xa5cc3c03994DB5b0d9A5eEdD10CabaB0813678AC', 123, '0x1234567890abcdef')]}
        result = chain_util.encode_transaction_data(w3=w3, functionAbi=function_abi, arguments=arguments)
        assert result == '0x34fcd5be000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000020000000000000000000000000a5cc3c03994db5b0d9a5eedd10cabab0813678ac000000000000000000000000000000000000000000000000000000000000007b000000000000000000000000000000000000000000000000000000000000006000000000000000000000000000000000000000000000000000000000000000081234567890abcdef000000000000000000000000000000000000000000000000'

    def test_burn_address_constant(self):
        assert chain_util.BURN_ADDRESS == '0x0000000000000000000000000000000000000000'
        assert len(chain_util.BURN_ADDRESS) == 42
        assert chain_util.BURN_ADDRESS.startswith('0x')
