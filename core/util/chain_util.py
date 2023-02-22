import eth_utils
from web3 import Web3
from web3.types import ChecksumAddress

BURN_ADDRESS = '0x0000000000000000000000000000000000000000'

def normalize_address(value: str) -> str:
    return str(normalize_address_checksum(value=value))

def normalize_address_checksum(value: str) -> ChecksumAddress:
    addressBytes = eth_utils.to_bytes(hexstr=value)
    return Web3.to_checksum_address(addressBytes[-20:])
