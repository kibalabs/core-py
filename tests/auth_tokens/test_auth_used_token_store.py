import datetime
import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from core.auth_tokens.auth_used_token_store import AuthUsedTokenStore
from core.auth_tokens.dict_auth_used_token_store import DictAuthUsedTokenStore
from core.auth_tokens.sql_auth_used_token_store import AuthUsedTokensMetadata
from core.auth_tokens.sql_auth_used_token_store import SqlAuthUsedTokenStore
from core.store.database import Database

PSQL_CONNECTION_STRING = os.environ.get('CORE_TEST_PSQL_CONNECTION_STRING')

pytestmark = pytest.mark.asyncio


# NOTE: postgres only runs when a connection string is given; skipping it instead breaks kiba-build's test-check report parsing
@pytest_asyncio.fixture(params=['dict', 'sqlite', 'postgresql'] if PSQL_CONNECTION_STRING else ['dict', 'sqlite'])
async def store(request, tmp_path) -> AsyncIterator[AuthUsedTokenStore]:
    if request.param == 'dict':
        yield DictAuthUsedTokenStore()
        return
    connectionString = PSQL_CONNECTION_STRING if request.param == 'postgresql' else Database.create_sqlite_connection_string(str(tmp_path / 'database.sqlite'))
    database = Database(connectionString=connectionString)
    await database.connect(poolSize=2)
    async with database.create_transaction() as connection:
        await connection.run_sync(AuthUsedTokensMetadata.drop_all)
        await connection.run_sync(AuthUsedTokensMetadata.create_all)
    yield SqlAuthUsedTokenStore(database=database)
    await database.disconnect()


async def test_a_key_can_only_be_marked_used_once_while_unexpired(store: AuthUsedTokenStore) -> None:
    assert not await store.is_used(key='code:1')
    assert await store.mark_used(key='code:1', lifetime=datetime.timedelta(minutes=1))
    assert not await store.mark_used(key='code:1', lifetime=datetime.timedelta(minutes=1))
    assert await store.is_used(key='code:1')
    assert await store.mark_used(key='code:2', lifetime=datetime.timedelta(minutes=1))


async def test_an_expired_key_can_be_marked_used_again(store: AuthUsedTokenStore) -> None:
    assert await store.mark_used(key='code:1', lifetime=datetime.timedelta(seconds=-1))
    assert not await store.is_used(key='code:1')
    assert await store.mark_used(key='code:1', lifetime=datetime.timedelta(minutes=1))
