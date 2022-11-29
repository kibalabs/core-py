import eth_utils
from web3 import Web3

BURN_ADDRESS = '0x0000000000000000000000000000000000000000'

def normalize_address(value: str) -> str:
    addressBytes = eth_utils.to_bytes(hexstr=value)
    return str(Web3.to_checksum_address(addressBytes[-20:]))
