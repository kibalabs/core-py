import datetime

from core.exceptions import InternalServerErrorException
from core.util import date_util
from core.web3.eth_client import RestEthClient


class EthClientRegistry:
    def __init__(self, archiveThresholdDays: int = 15) -> None:
        self.archiveThresholdDays = archiveThresholdDays
        self.ethClientsByChainId: dict[int, RestEthClient] = {}
        self.archiveEthClientsByChainId: dict[int, RestEthClient] = {}
        self.paymasterEthClientsByChainId: dict[int, RestEthClient] = {}

    def register_client(self, client: RestEthClient) -> None:
        self.ethClientsByChainId[client.chainId] = client

    def register_archive_client(self, client: RestEthClient) -> None:
        self.archiveEthClientsByChainId[client.chainId] = client

    def register_paymaster_client(self, client: RestEthClient) -> None:
        self.paymasterEthClientsByChainId[client.chainId] = client

    def get_client(self, chainId: int, date: datetime.date | None = None) -> RestEthClient:
        # NOTE(krishan711): regular nodes may have pruned state older than the threshold so those reads go to the archive node
        dateDiff = date_util.calculate_diff_days(startDate=date_util.datetime_from_date(date=date), endDate=date_util.datetime_from_now()) if date is not None else 0
        if dateDiff > self.archiveThresholdDays:
            return self.get_archive_client(chainId=chainId)
        return self.get_regular_client(chainId=chainId)

    def get_paymaster_client(self, chainId: int) -> RestEthClient:
        if chainId not in self.paymasterEthClientsByChainId:
            raise InternalServerErrorException(f'Chain {chainId} does not have a paymaster client')
        return self.paymasterEthClientsByChainId[chainId]

    def get_archive_client(self, chainId: int) -> RestEthClient:
        if chainId not in self.archiveEthClientsByChainId:
            raise InternalServerErrorException(f'Chain {chainId} does not have an archive client')
        return self.archiveEthClientsByChainId[chainId]

    def get_regular_client(self, chainId: int) -> RestEthClient:
        if chainId in self.ethClientsByChainId:
            return self.ethClientsByChainId[chainId]
        if chainId in self.archiveEthClientsByChainId:
            return self.archiveEthClientsByChainId[chainId]
        raise InternalServerErrorException(f'Chain {chainId} does not have a regular client or an archive client')
