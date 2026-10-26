import asyncio
import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
import sqlalchemy
from sqlalchemy import Column
from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import text
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import StreamingResponse
from starlette.routing import Route

from core.api.middleware.database_connection_middleware import DatabaseConnectionMiddleware
from core.store.database import Database

PSQL_CONNECTION_STRING = os.environ.get('CORE_TEST_PSQL_CONNECTION_STRING')

metadata = MetaData()
records = Table(f'records_{uuid.uuid4().hex}', metadata, Column('name', sqlalchemy.Text, primary_key=True))


@pytest_asyncio.fixture(params=['sqlite', 'postgresql'] if PSQL_CONNECTION_STRING else ['sqlite'])
async def database(request, tmp_path):
    connectionString = PSQL_CONNECTION_STRING if request.param == 'postgresql' else Database.create_sqlite_connection_string(str(tmp_path / 'database.sqlite'))
    database = Database(connectionString=connectionString)
    await database.connect(poolSize=2)
    async with database.create_transaction() as connection:
        await connection.run_sync(metadata.drop_all)
        await connection.run_sync(metadata.create_all)
    yield database
    async with database.create_transaction() as connection:
        await connection.run_sync(metadata.drop_all)
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


async def post_to_app(app) -> tuple[int, bytes]:
    scope = {
        'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': 'POST', 'scheme': 'http', 'path': '/', 'raw_path': b'/',
        'root_path': '', 'query_string': b'', 'headers': [], 'client': ('127.0.0.1', 1), 'server': ('test', 80),
    }
    isRequestSent = False
    responseFinished = asyncio.Event()
    statusHolder: list[int] = []
    bodyParts: list[bytes] = []

    async def receive():
        nonlocal isRequestSent
        if not isRequestSent:
            isRequestSent = True
            return {'type': 'http.request', 'body': b'', 'more_body': False}
        await responseFinished.wait()
        return {'type': 'http.disconnect'}

    async def send(message):
        if message['type'] == 'http.response.start':
            statusHolder.append(message['status'])
        elif message['type'] == 'http.response.body':
            bodyParts.append(message.get('body', b''))
            if not message.get('more_body', False):
                responseFinished.set()

    await app(scope, receive, send)
    responseFinished.set()
    return (statusHolder or [0])[0], b''.join(bodyParts)


@pytest.mark.asyncio
async def test_streaming_through_base_http_middleware_does_not_query_the_connection_concurrently(database):
    # NOTE(krishan711): BaseHTTPMiddleware runs the route in another task, so the stream is still running queries when
    # the response start reaches DatabaseConnectionMiddleware and it commits
    async def stream() -> AsyncIterator[bytes]:
        for index in range(20):
            if database.get_dialect_name() == 'postgresql':
                await database.execute(text('SELECT pg_sleep(0.005)'))
            await database.execute(insert(records).values(name=f'event-{index:02d}'))
            yield b'event\n'

    async def endpoint(request: Request) -> StreamingResponse:
        await database.execute(insert(records).values(name='request'))
        return StreamingResponse(stream())

    async def passthrough(request, callNext):
        return await callNext(request)

    app = Starlette(
        routes=[Route('/', endpoint=endpoint, methods=['POST'])],
        middleware=[
            Middleware(DatabaseConnectionMiddleware, database=database),
            Middleware(BaseHTTPMiddleware, dispatch=passthrough),
        ],
    )
    for _ in range(5):
        status, body = await post_to_app(app=app)
        assert status == 200
        assert body == b'event\n' * 20
        assert len(await get_record_names(database=database)) == 21
        async with database.create_transaction() as connection:
            await connection.execute(records.delete())

    async with database.create_transaction() as connection:
        await connection.execute(insert(records).values(name='check'))
    assert await get_record_names(database=database) == ['check']
