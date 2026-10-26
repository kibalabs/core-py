import pytest
import pytest_asyncio
import sqlalchemy
from sqlalchemy import Column
from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy import insert
from sqlalchemy import select

from core.api.middleware.database_connection_middleware import DatabaseConnectionMiddleware
from core.store.database import Database

metadata = MetaData()
records = Table('records', metadata, Column('name', sqlalchemy.Text, primary_key=True))


@pytest_asyncio.fixture
async def database(tmp_path):
    database = Database(connectionString=Database.create_sqlite_connection_string(str(tmp_path / 'database.sqlite')))
    await database.connect(poolSize=2)
    async with database.create_transaction() as connection:
        await connection.run_sync(metadata.create_all)
    yield database
    await database.disconnect()


async def get_record_names(database: Database) -> list[str]:
    async with database.create_transaction() as connection:
        result = await database.execute(select(records.c.name).order_by(records.c.name), connection=connection)
    return list(result.scalars().all())


async def call_app(app, database: Database) -> list[tuple[str, list[str]]]:
    sentMessages: list[tuple[str, list[str]]] = []

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    async def send(message):
        sentMessages.append((message['type'], await get_record_names(database=database)))

    await DatabaseConnectionMiddleware(app=app, database=database)({'type': 'http', 'method': 'POST', 'path': '/'}, receive, send)
    return sentMessages


@pytest.mark.asyncio
async def test_writes_are_committed_before_the_response_starts(database):
    async def app(scope, receive, send):
        await database.execute(insert(records).values(name='request'))
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'ok'})

    sentMessages = await call_app(app=app, database=database)

    assert sentMessages == [('http.response.start', ['request']), ('http.response.body', ['request'])]


@pytest.mark.asyncio
async def test_writes_while_streaming_are_committed_when_the_request_ends(database):
    async def app(scope, receive, send):
        await database.execute(insert(records).values(name='before'))
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await database.execute(insert(records).values(name='streaming'))
        await send({'type': 'http.response.body', 'body': b'ok'})

    sentMessages = await call_app(app=app, database=database)

    assert sentMessages == [('http.response.start', ['before']), ('http.response.body', ['before'])]
    assert await get_record_names(database=database) == ['before', 'streaming']


@pytest.mark.asyncio
async def test_writes_are_rolled_back_when_the_request_fails_before_responding(database):
    async def app(scope, receive, send):
        await database.execute(insert(records).values(name='request'))
        raise ValueError('failed')

    with pytest.raises(ValueError, match='failed'):
        await call_app(app=app, database=database)

    assert await get_record_names(database=database) == []
