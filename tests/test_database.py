import datetime

import pytest
import sqlalchemy
from sqlalchemy import JSON
from sqlalchemy import Column
from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import text

from core.exceptions import InternalServerErrorException
from core.store.database import Database
from core.util import json_util


@pytest.fixture
def database(tmp_path):
    return Database(connectionString=Database.create_sqlite_connection_string(str(tmp_path / 'database.sqlite')))


@pytest.mark.parametrize(
    ('engine', 'username', 'password', 'host', 'port', 'name', 'expected'),
    [
        ('postgresql+asyncpg', 'user', 'password', 'localhost', '5432', 'core', 'postgresql+asyncpg://user:password@localhost:5432/core'),
    ],
)
def test_create_connection_string(engine, username, password, host, port, name, expected):
    assert Database.create_connection_string(engine, username, password, host, port, name) == expected


def test_create_psql_connection_string():
    assert Database.create_psql_connection_string('user', 'password', 'localhost', '5432', 'core') == 'postgresql+asyncpg://user:password@localhost:5432/core'


def test_create_sqlite_connection_string():
    assert Database.create_sqlite_connection_string('database.sqlite') == 'sqlite+aiosqlite:///database.sqlite'


@pytest.mark.asyncio
async def test_connect_is_idempotent_and_disconnect_clears_engine(database):
    await database.connect(poolSize=1)
    engine = database._engine

    await database.connect(poolSize=2)

    assert database._engine is engine
    assert database._engine.sync_engine.dialect._json_serializer is json_util.dumps
    assert database._engine.sync_engine.dialect._json_deserializer is json_util.loads

    await database.disconnect()
    assert database._engine is None
    await database.disconnect()


@pytest.mark.asyncio
async def test_create_transaction_requires_connection(database):
    with pytest.raises(InternalServerErrorException, match='Engine has not been established'):
        async with database.create_transaction():
            pass


@pytest.mark.asyncio
async def test_execute_requires_connection(database):
    with pytest.raises(InternalServerErrorException, match='Connection has not been established'):
        await database.execute(text('SELECT 1'))


@pytest.mark.asyncio
async def test_json_values_round_trip_through_sqlalchemy(database):
    metadata = MetaData()
    records = Table(
        'records',
        metadata,
        Column('id', sqlalchemy.Integer, primary_key=True),
        Column('payload', JSON, nullable=False),
    )
    payload = {
        'createdAt': datetime.datetime(2025, 1, 2, 3, 4, 5),
        'message': 'Hello 🌍',
        'nested': {'enabled': True, 'values': [None, 1, 2.5]},
    }

    await database.connect(poolSize=1)
    async with database.create_transaction() as connection:
        await connection.run_sync(metadata.create_all)
        await database.execute(insert(records).values(payload=payload), connection=connection)
        result = await database.execute(select(records.c.payload), connection=connection)

    assert result.scalar_one() == {
        'createdAt': '2025-01-02T03:04:05',
        'message': 'Hello 🌍',
        'nested': {'enabled': True, 'values': [None, 1, 2.5]},
    }
    await database.disconnect()


@pytest.mark.asyncio
async def test_context_connection_is_used_by_execute(database):
    await database.connect(poolSize=1)

    async with database.create_context_connection() as connection:
        result = await database.execute(text('SELECT 42 AS answer'))
        assert result.scalar_one() == 42
        assert database._get_context_connection() is connection

    assert database._get_context_connection() is None
    await database.disconnect()


@pytest.mark.asyncio
async def test_context_connection_cannot_be_nested(database):
    await database.connect(poolSize=1)

    with pytest.raises(InternalServerErrorException, match='Connection has already been established'):
        async with database.create_context_connection():
            async with database.create_context_connection():
                pass

    await database.disconnect()
