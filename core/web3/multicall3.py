# mypy: disable-error-code="typeddict-unknown-key, misc, list-item, typeddict-item"

from eth_typing import ABI

# Get from https://www.multicall3.com/deployments
CHAIN_ID_MULTICALL3_ADDRESS_MAP: dict[int, str] = {
    1: '0xcA11bde05977b3631167028862bE2a173976CA11',
    8453: '0xcA11bde05977b3631167028862bE2a173976CA11',
    84532: '0xcA11bde05977b3631167028862bE2a173976CA11',
}

MULTICALL3_ABI: ABI = [
    {
        'inputs': [
            {
                'components': [
                    {'name': 'target', 'type': 'address'},
                    {'name': 'allowFailure', 'type': 'bool'},
                    {'name': 'callData', 'type': 'bytes'},
                ],
                'name': 'calls',
                'type': 'tuple[]',
            }
        ],
        'name': 'aggregate3',
        'outputs': [
            {
                'components': [
                    {'name': 'success', 'type': 'bool'},
                    {'name': 'returnData', 'type': 'bytes'},
                ],
                'name': 'returnData',
                'type': 'tuple[]',
            }
        ],
        'stateMutability': 'payable',
        'type': 'function',
    },
]
