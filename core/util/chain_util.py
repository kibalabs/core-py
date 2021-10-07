import eth_utils
from web3 import Web3


def normalize_address(value: str) -> str:
    addressBytes = eth_utils.to_bytes(hexstr=value)
    return Web3.toChecksumAddress(addressBytes[-20:])
