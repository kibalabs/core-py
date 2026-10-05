import datetime
import os
import typing
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
import sqlalchemy
from pydantic import BaseModel

from core.exceptions import KibaException
from core.exceptions import NotFoundException
from core.store.database import Database
from core.store.entity_repository import EntityRepository
from core.store.retriever import DateFieldFilter
from core.store.retriever import Direction
from core.store.retriever import IntegerFieldFilter
from core.store.retriever import Order
from core.store.retriever import StringFieldFilter
from core.store.retriever import UUIDFieldFilter

PSQL_CONNECTION_STRING = os.environ.get('CORE_TEST_PSQL_CONNECTION_STRING')

pytestmark = pytest.mark.asyncio

metadata = sqlalchemy.MetaData()

ItemsTable = sqlalchemy.Table(
    'tbl_entity_repository_items',
    metadata,
    sqlalchemy.Column(key='itemId', name='id', type_=sqlalchemy.Uuid, primary_key=True),
    sqlalchemy.Column(key='createdDate', name='created_date', type_=sqlalchemy.DateTime, nullable=False),
    sqlalchemy.Column(key='updatedDate', name='updated_date', type_=sqlalchemy.DateTime, nullable=False),
    sqlalchemy.Column(key='name', name='name', type_=sqlalchemy.Text, nullable=False, unique=True),
    sqlalchemy.Column(key='count', name='count', type_=sqlalchemy.Integer, nullable=False),
    sqlalchemy.Column(key='amount', name='amount', type_=sqlalchemy.Numeric(precision=78, scale=0), nullable=False),
    sqlalchemy.Column(key='expiryDate', name='expiry_date', type_=sqlalchemy.DateTime, nullable=True),
    sqlalchemy.Column(key='details', name='details', type_=sqlalchemy.JSON, nullable=True),
)

EventsTable = sqlalchemy.Table(
    'tbl_entity_repository_events',
    metadata,
    sqlalchemy.Column(key='eventId', name='id', type_=sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column(key='createdDate', name='created_date', type_=sqlalchemy.DateTime, nullable=False),
    sqlalchemy.Column(key='name', name='name', type_=sqlalchemy.Text, nullable=False),
)


class ItemDetails(BaseModel):
    color: str


class Item(BaseModel):
    itemId: str
    createdDate: datetime.datetime
    updatedDate: datetime.datetime
    name: str
    count: int
    amount: int
    expiryDate: datetime.datetime | None
    details: ItemDetails | None


class Event(BaseModel):
    eventId: int
    createdDate: datetime.datetime
    name: str


class UpperNameEntityRepository(EntityRepository[Item]):
    def _convert_value_to_db(self, column: sqlalchemy.Column[typing.Any], value: typing.Any | None) -> typing.Any | None:  # type: ignore[explicit-any]
        value = super()._convert_value_to_db(column=column, value=value)
        if column.key == 'name' and value is not None:
            value = value.upper()
        return value


class CountedItem(Item):
    doubleCount: int


class CountedItemEntityRepository(EntityRepository[CountedItem]):
    def __init__(self) -> None:
        super().__init__(table=ItemsTable, modelClass=CountedItem)
        self.doubleCountColumn = (ItemsTable.c.count * 2).label('doubleCount')

    def list_select_columns(self) -> list[sqlalchemy.ColumnElement[typing.Any]]:  # type: ignore[explicit-any]
        return [*self.table.columns, self.doubleCountColumn]

    def _get_field_values(self, row: sqlalchemy.RowMapping) -> dict[str, typing.Any]:  # type: ignore[explicit-any]
        return {**super()._get_field_values(row=row), 'doubleCount': row[self.doubleCountColumn.key]}


ItemsRepository = EntityRepository(table=ItemsTable, modelClass=Item)
EventsRepository = EntityRepository(table=EventsTable, modelClass=Event)


# NOTE: postgres only runs when a connection string is given; skipping it instead breaks kiba-build's test-check report parsing
@pytest_asyncio.fixture(params=['sqlite', 'postgresql'] if PSQL_CONNECTION_STRING else ['sqlite'])
async def database(request, tmp_path) -> AsyncIterator[Database]:
    connectionString = PSQL_CONNECTION_STRING if request.param == 'postgresql' else Database.create_sqlite_connection_string(str(tmp_path / 'database.sqlite'))
    database = Database(connectionString=connectionString)
    await database.connect(poolSize=1)
    async with database.create_transaction() as connection:
        await connection.run_sync(metadata.drop_all)
        await connection.run_sync(metadata.create_all)
    yield database
    await database.disconnect()


async def _create_item(database: Database, name: str, count: int = 1, amount: int = 1, expiryDate: datetime.datetime | None = None) -> Item:
    async with database.create_transaction() as connection:
        return await ItemsRepository.create(database=database, connection=connection, name=name, count=count, amount=amount, expiryDate=expiryDate)


async def test_create_generates_id_and_dates(database: Database):
    item = await _create_item(database=database, name='a')
    assert len(item.itemId) == 36
    assert item.createdDate.tzinfo == datetime.UTC
    assert item.updatedDate == item.createdDate
    async with database.create_transaction() as connection:
        assert await ItemsRepository.get(database=database, connection=connection, idValue=item.itemId) == item


async def test_create_dumps_pydantic_json_values(database: Database):
    async with database.create_transaction() as connection:
        item = await ItemsRepository.create(database=database, connection=connection, name='a', count=1, amount=1, details=ItemDetails(color='red'))
    assert item.details == ItemDetails(color='red')


async def test_create_rejects_unknown_columns(database: Database):
    async with database.create_transaction() as connection:
        with pytest.raises(KibaException, match='Unknown column: unknown'):
            await ItemsRepository.create(database=database, connection=connection, name='a', count=1, amount=1, unknown=1)


async def test_create_without_updated_date_column(database: Database):
    async with database.create_transaction() as connection:
        event = await EventsRepository.create(database=database, connection=connection, name='started')
    assert event.name == 'started'
    assert event.createdDate.tzinfo == datetime.UTC


async def test_get_raises_not_found(database: Database):
    async with database.create_transaction() as connection:
        with pytest.raises(NotFoundException):
            await ItemsRepository.get(database=database, connection=connection, idValue='00000000-0000-0000-0000-000000000000')


async def test_update_changes_values_and_updated_date(database: Database):
    item = await _create_item(database=database, name='a')
    async with database.create_transaction() as connection:
        updatedItem = await ItemsRepository.update(database=database, connection=connection, itemId=item.itemId, count=5)
    assert updatedItem.count == 5
    assert updatedItem.createdDate == item.createdDate
    assert updatedItem.updatedDate >= item.updatedDate


async def test_update_requires_id(database: Database):
    async with database.create_transaction() as connection:
        with pytest.raises(KibaException, match='Failed to find id value'):
            await ItemsRepository.update(database=database, connection=connection, count=5)


async def test_upsert_inserts_then_updates(database: Database):
    async with database.create_transaction() as connection:
        item = await ItemsRepository.upsert(database=database, connection=connection, constraintColumnNames=['name'], name='a', count=1, amount=1)
        upsertedItem = await ItemsRepository.upsert(database=database, connection=connection, constraintColumnNames=['name'], name='a', count=2, amount=1)
    assert upsertedItem.itemId == item.itemId
    assert upsertedItem.createdDate == item.createdDate
    assert upsertedItem.count == 2


async def test_upsert_many_inserts_and_updates(database: Database):
    item = await _create_item(database=database, name='a')
    async with database.create_transaction() as connection:
        items = await ItemsRepository.upsert_many(database=database, connection=connection, constraintColumnNames=['name'], rowDicts=[{'name': 'a', 'count': 3, 'amount': 1}, {'name': 'b', 'count': 4, 'amount': 1}])
        assert await ItemsRepository.upsert_many(database=database, connection=connection, constraintColumnNames=['name'], rowDicts=[]) == []
    itemsByName = {upsertedItem.name: upsertedItem for upsertedItem in items}
    assert itemsByName['a'].itemId == item.itemId
    assert itemsByName['a'].createdDate == item.createdDate
    assert itemsByName['a'].count == 3
    assert itemsByName['b'].count == 4


async def test_list_many_filters_orders_and_pages(database: Database):
    for index in range(4):
        await _create_item(database=database, name=f'item-{index}', count=index)
    async with database.create_transaction() as connection:
        items = await ItemsRepository.list_many(database=database, connection=connection, fieldFilters=[IntegerFieldFilter(fieldName='count', gte=1)], orders=[Order(fieldName='count', direction=Direction.DESCENDING)], limit=2, offset=1)
    assert [item.count for item in items] == [2, 1]


async def test_uuid_field_filter_accepts_strings_and_uuids(database: Database):
    item = await _create_item(database=database, name='a')
    await _create_item(database=database, name='b')
    async with database.create_transaction() as connection:
        items = await ItemsRepository.list_many(database=database, connection=connection, fieldFilters=[UUIDFieldFilter(fieldName='itemId', containedIn=[item.itemId])])
        notItems = await ItemsRepository.list_many(database=database, connection=connection, fieldFilters=[UUIDFieldFilter(fieldName='itemId', ne=item.itemId)])
    assert [listedItem.itemId for listedItem in items] == [item.itemId]
    assert [listedItem.name for listedItem in notItems] == ['b']


async def test_date_field_filter_accepts_aware_datetimes(database: Database):
    expiryDate = datetime.datetime(2026, 1, 1, 12, tzinfo=datetime.UTC)
    item = await _create_item(database=database, name='a', expiryDate=expiryDate)
    await _create_item(database=database, name='b', expiryDate=expiryDate + datetime.timedelta(days=1))
    offsetTimezone = datetime.timezone(datetime.timedelta(hours=2))
    async with database.create_transaction() as connection:
        items = await ItemsRepository.list_many(database=database, connection=connection, fieldFilters=[DateFieldFilter(fieldName='expiryDate', lte=expiryDate.astimezone(offsetTimezone))])
    assert [listedItem.itemId for listedItem in items] == [item.itemId]
    assert items[0].expiryDate == expiryDate


async def test_integer_field_filter_keeps_column_type(database: Database):
    # NOTE: sqlite stores integers as int64, postgres numeric columns can go beyond that
    largeAmount = 2**100 if database.get_dialect_name() == 'postgresql' else 2**40
    item = await _create_item(database=database, name='a', amount=largeAmount)
    await _create_item(database=database, name='b', amount=1)
    async with database.create_transaction() as connection:
        items = await ItemsRepository.list_many(database=database, connection=connection, fieldFilters=[IntegerFieldFilter(fieldName='amount', eq=largeAmount)])
        containedItems = await ItemsRepository.list_many(database=database, connection=connection, fieldFilters=[IntegerFieldFilter(fieldName='amount', containedIn=[largeAmount])])
    assert [listedItem.itemId for listedItem in items] == [item.itemId]
    assert [listedItem.itemId for listedItem in containedItems] == [item.itemId]
    assert items[0].amount == largeAmount


async def test_get_first_get_one_and_get_one_or_none(database: Database):
    await _create_item(database=database, name='a', count=1)
    await _create_item(database=database, name='b', count=2)
    async with database.create_transaction() as connection:
        firstItem = await ItemsRepository.get_first(database=database, connection=connection, orders=[Order(fieldName='count', direction=Direction.DESCENDING)])
        item = await ItemsRepository.get_one(database=database, connection=connection, fieldFilters=[StringFieldFilter(fieldName='name', eq='a')])
        missingItem = await ItemsRepository.get_one_or_none(database=database, connection=connection, fieldFilters=[StringFieldFilter(fieldName='name', eq='c')])
    assert firstItem is not None
    assert firstItem.name == 'b'
    assert item.name == 'a'
    assert missingItem is None


async def test_delete_removes_filtered_rows(database: Database):
    await _create_item(database=database, name='a')
    await _create_item(database=database, name='b')
    async with database.create_transaction() as connection:
        await ItemsRepository.delete(database=database, connection=connection, fieldFilters=[StringFieldFilter(fieldName='name', eq='a')])
        items = await ItemsRepository.list_many(database=database, connection=connection)
    assert [item.name for item in items] == ['b']


async def test_subclasses_can_add_conversions(database: Database):
    repository = UpperNameEntityRepository(table=ItemsTable, modelClass=Item)
    async with database.create_transaction() as connection:
        item = await repository.create(database=database, connection=connection, name='a', count=1, amount=1)
    assert item.name == 'A'


async def test_subclasses_can_select_extra_columns(database: Database):
    repository = CountedItemEntityRepository()
    async with database.create_transaction() as connection:
        item = await repository.create(database=database, connection=connection, name='a', count=2, amount=1)
        updatedItem = await repository.update(database=database, connection=connection, itemId=item.itemId, count=3)
        listedItems = await repository.list_many(database=database, connection=connection)
    assert item.doubleCount == 4
    assert updatedItem.doubleCount == 6
    assert [listedItem.doubleCount for listedItem in listedItems] == [6]
