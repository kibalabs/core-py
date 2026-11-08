import datetime
import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from core.claims.claim_store import ClaimStore
from core.claims.dict_claim_store import DictClaimStore
from core.claims.sql_claim_store import ClaimsMetadata
from core.claims.sql_claim_store import SqlClaimStore
from core.store.database import Database

PSQL_CONNECTION_STRING = os.environ.get('CORE_TEST_PSQL_CONNECTION_STRING')

pytestmark = pytest.mark.asyncio


# NOTE: postgres only runs when a connection string is given; skipping it instead breaks kiba-build's test-check report parsing
@pytest_asyncio.fixture(params=['dict', 'sqlite', 'postgresql'] if PSQL_CONNECTION_STRING else ['dict', 'sqlite'])
async def store(request, tmp_path) -> AsyncIterator[ClaimStore]:
    if request.param == 'dict':
        yield DictClaimStore()
        return
    connectionString = PSQL_CONNECTION_STRING if request.param == 'postgresql' else Database.create_sqlite_connection_string(str(tmp_path / 'database.sqlite'))
    database = Database(connectionString=connectionString)
    await database.connect(poolSize=2)
    async with database.create_transaction() as connection:
        await connection.run_sync(ClaimsMetadata.drop_all)
        await connection.run_sync(ClaimsMetadata.create_all)
    yield SqlClaimStore(database=database)
    await database.disconnect()


async def test_a_key_can_only_be_claimed_once_while_unexpired(store: ClaimStore) -> None:
    assert not await store.is_claimed(key='code:1')
    assert await store.claim(key='code:1', lifetime=datetime.timedelta(minutes=1))
    assert not await store.claim(key='code:1', lifetime=datetime.timedelta(minutes=1))
    assert await store.is_claimed(key='code:1')
    assert await store.claim(key='code:2', lifetime=datetime.timedelta(minutes=1))


async def test_an_expired_key_can_be_claimed_again(store: ClaimStore) -> None:
    assert await store.claim(key='code:1', lifetime=datetime.timedelta(seconds=-1))
    assert not await store.is_claimed(key='code:1')
    assert await store.claim(key='code:1', lifetime=datetime.timedelta(minutes=1))
