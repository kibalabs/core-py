import datetime

import pytest

from core.exceptions import InternalServerErrorException
from core.requester import Requester
from core.util import date_util
from core.web3.eth_client import RestEthClient
from core.web3.eth_client_registry import EthClientRegistry


def _client(chainId: int) -> RestEthClient:
    return RestEthClient(url=f'https://rpc-{chainId}.test', requester=Requester(), chainId=chainId)


def _days_ago(days: int) -> datetime.date:
    return date_util.datetime_from_now(days=-days).date()


def test_get_client_uses_regular_client_for_recent_dates():
    registry = EthClientRegistry()
    regularClient = _client(chainId=8453)
    archiveClient = _client(chainId=8453)
    registry.register_client(client=regularClient)
    registry.register_archive_client(client=archiveClient)
    assert registry.get_client(chainId=8453) is regularClient
    assert registry.get_client(chainId=8453, date=_days_ago(days=15)) is regularClient
    assert registry.get_client(chainId=8453, date=_days_ago(days=16)) is archiveClient


def test_get_client_respects_archive_threshold():
    registry = EthClientRegistry(archiveThresholdDays=2)
    regularClient = _client(chainId=8453)
    archiveClient = _client(chainId=8453)
    registry.register_client(client=regularClient)
    registry.register_archive_client(client=archiveClient)
    assert registry.get_client(chainId=8453, date=_days_ago(days=2)) is regularClient
    assert registry.get_client(chainId=8453, date=_days_ago(days=3)) is archiveClient


def test_get_regular_client_falls_back_to_archive_client():
    registry = EthClientRegistry()
    archiveClient = _client(chainId=1)
    registry.register_archive_client(client=archiveClient)
    assert registry.get_regular_client(chainId=1) is archiveClient


def test_missing_clients_raise():
    registry = EthClientRegistry()
    registry.register_client(client=_client(chainId=1))
    with pytest.raises(InternalServerErrorException):
        registry.get_regular_client(chainId=8453)
    with pytest.raises(InternalServerErrorException):
        registry.get_archive_client(chainId=1)
    with pytest.raises(InternalServerErrorException):
        registry.get_paymaster_client(chainId=1)


def test_get_paymaster_client():
    registry = EthClientRegistry()
    paymasterClient = _client(chainId=8453)
    registry.register_paymaster_client(client=paymasterClient)
    assert registry.get_paymaster_client(chainId=8453) is paymasterClient
