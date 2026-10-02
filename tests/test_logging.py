import datetime
import json
import logging as pythonLogging
from collections.abc import Iterator

import pytest

from core import logging
from core.exceptions import NotFoundException
from core.util.value_holder import RequestIdHolder

APP_LOGGER_NAME = 'test-app-library'
CORE_LOGGER_NAMES = [logFormat.loggerType for logFormat in logging.ALL_LOGGER_FORMATS]


@pytest.fixture(autouse=True)
def restore_logging_state() -> Iterator[None]:
    externalLoggerNames = [*logging.DEFAULT_EXTERNAL_LOGGER_NAMES, APP_LOGGER_NAME]
    originalExternalLevels = {loggerName: pythonLogging.getLogger(loggerName).level for loggerName in externalLoggerNames}
    originalCoreState = {loggerName: (pythonLogging.getLogger(loggerName).handlers, pythonLogging.getLogger(loggerName).level, pythonLogging.getLogger(loggerName).propagate) for loggerName in CORE_LOGGER_NAMES}
    for loggerName in externalLoggerNames:
        pythonLogging.getLogger(loggerName).setLevel(pythonLogging.NOTSET)
    yield
    for loggerName, level in originalExternalLevels.items():
        pythonLogging.getLogger(loggerName).setLevel(level)
    for loggerName, (handlers, level, propagate) in originalCoreState.items():
        logger = pythonLogging.getLogger(loggerName)
        logger.handlers, logger.propagate = handlers, propagate
        logger.setLevel(level)


def _levels(loggerNames: list[str]) -> list[int]:
    return [pythonLogging.getLogger(loggerName).level for loggerName in loggerNames]


def _lines(capsys: pytest.CaptureFixture[str]) -> list[str]:
    return capsys.readouterr().out.splitlines()


def _json_lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    return [json.loads(line) for line in _lines(capsys)]


class TestExternalLoggers:
    def test_init_quietens_core_external_loggers_by_default(self) -> None:
        logging.init_basic_logging()
        assert _levels(['httpx2', 'sqlalchemy', APP_LOGGER_NAME]) == [pythonLogging.WARNING, pythonLogging.WARNING, pythonLogging.NOTSET]

    def test_extra_logger_names_are_added_to_the_defaults(self) -> None:
        logging.init_basic_logging(extraLoggerNames=[APP_LOGGER_NAME])
        assert _levels(['httpx2', APP_LOGGER_NAME]) == [pythonLogging.WARNING, pythonLogging.WARNING]

    def test_logger_names_replace_the_defaults(self) -> None:
        logging.init_basic_logging(loggerNames=[APP_LOGGER_NAME])
        assert _levels(['httpx2', APP_LOGGER_NAME]) == [pythonLogging.NOTSET, pythonLogging.WARNING]

    def test_every_init_function_applies_the_logger_names(self) -> None:
        logging.init_logging(name='app', version='v1', environment='test', extraLoggerNames=[APP_LOGGER_NAME])
        assert _levels(['httpx2', APP_LOGGER_NAME]) == [pythonLogging.WARNING, pythonLogging.WARNING]
        pythonLogging.getLogger(APP_LOGGER_NAME).setLevel(pythonLogging.NOTSET)
        logging.init_json_logging(name='app', version='v1', environment='test', loggerNames=[APP_LOGGER_NAME])
        assert pythonLogging.getLogger(APP_LOGGER_NAME).level == pythonLogging.WARNING

    def test_init_external_loggers_uses_the_given_level(self) -> None:
        logging.init_external_loggers(extraLoggerNames=[APP_LOGGER_NAME], loggingLevel=pythonLogging.ERROR)
        assert _levels(['httpx2', APP_LOGGER_NAME]) == [pythonLogging.ERROR, pythonLogging.ERROR]

    def test_external_logger_level_applies_to_child_loggers(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_basic_logging()
        pythonLogging.getLogger('sqlalchemy.engine').info('noisy query log')
        pythonLogging.getLogger('sqlalchemy.engine').warning('important warning')
        assert _lines(capsys) == ['important warning']


class TestBasicLogging:
    def test_logs_info_and_above_but_not_debug(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_basic_logging()
        logging.debug('debug line')
        logging.info('info line')
        logging.warning('warning line')
        logging.error('error line')
        logging.critical('critical line')
        assert _lines(capsys) == ['info line', 'warning line', 'error line', 'critical line']

    def test_show_debug_includes_debug(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_basic_logging(showDebug=True)
        logging.debug('debug line')
        assert _lines(capsys) == ['debug line']

    def test_messages_are_formatted_with_args(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_basic_logging()
        logging.info('hello %s, you are %d', 'kiba', 3)
        assert _lines(capsys) == ['hello kiba, you are 3']

    def test_core_loggers_do_not_propagate_to_avoid_duplicate_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_basic_logging()
        logging.init_basic_logging()
        logging.stat(name='events', key='created')
        assert _lines(capsys) == ['events:created:1']


class TestStat:
    def test_logs_name_key_and_value(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_basic_logging()
        logging.stat(name='events', key='created', value=2.5)
        assert _lines(capsys) == ['events:created:2.5']

    def test_escapes_separators_and_rounds_values(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_basic_logging()
        logging.stat(name='db:query', key='user:read', value=1.23456789)
        logging.stat(name='whole', key='number', value=3.0)
        assert _lines(capsys) == ['db__query:user__read:1.234568', 'whole:number:3']

    def test_nothing_is_logged_when_the_stat_logger_is_disabled(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_basic_logging()
        logging.STAT_LOGGER.setLevel(pythonLogging.WARNING)
        logging.stat(name='events', key='created')
        assert _lines(capsys) == []


class TestApi:
    def test_logs_action_path_query_response_and_duration(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_basic_logging()
        logging.api(action='GET', path='/v1/users', query='limit=10', response=200, duration=0.25)
        assert _lines(capsys) == ['GET:/v1/users:limit=10:200:0.25']

    def test_missing_response_and_duration_are_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_basic_logging()
        logging.api(action='CRON', path='job', query='')
        assert _lines(capsys) == ['CRON:job:::']

    def test_escapes_separators(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_basic_logging()
        logging.api(action='MESSAGE', path='a:b', query='x=1:2')
        assert _lines(capsys) == ['MESSAGE:a__b:x=1__2::']

    def test_nothing_is_logged_when_the_api_logger_is_disabled(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_basic_logging()
        logging.API_LOGGER.setLevel(pythonLogging.WARNING)
        logging.api(action='GET', path='/', query='')
        assert _lines(capsys) == []


class TestException:
    def test_logs_kiba_exception_message_with_traceback(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_basic_logging()
        try:
            raise NotFoundException(message='user not found')
        except NotFoundException as exception:
            logging.exception(exception)
        lines = _lines(capsys)
        assert lines[0] == 'user not found'
        assert lines[1] == 'Traceback (most recent call last):'
        assert lines[-1].endswith("message='user not found')")

    def test_logs_plain_exception_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_basic_logging()
        try:
            raise ValueError('bad value')
        except ValueError as exception:
            logging.exception(exception)
        lines = _lines(capsys)
        assert (lines[0], lines[-1]) == ('bad value', 'ValueError: bad value')

    def test_logs_string_message_without_traceback_when_disabled(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_basic_logging()
        logging.exception('something failed', exc_info=False)
        assert _lines(capsys) == ['something failed']


class TestTextLogging:
    def test_includes_service_details_request_id_level_and_location(self, capsys: pytest.CaptureFixture[str]) -> None:
        requestIdHolder = RequestIdHolder()
        requestIdHolder.set_value(value='req-123')
        logging.init_logging(name='app', version='v1', environment='test', requestIdHolder=requestIdHolder)
        logging.warning('hello')
        parts = _lines(capsys)[0].split(' - ')
        datetime.datetime.strptime(parts[0], '%Y-%m-%dT%H:%M:%S.%f')  # noqa: DTZ007
        assert parts[1:8] == ['KIBA_1', 'app', 'v1', 'test', 'req-123', 'WARNING', 'root']
        assert parts[8].startswith('tests.test_logging.py:test_includes_service_details_request_id_level_and_location:')
        assert parts[9] == 'hello'

    def test_stat_api_and_exception_report_the_caller_location(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_logging(name='app', version='v1', environment='test')
        logging.stat(name='events', key='created')
        logging.api(action='GET', path='/', query='')
        logging.exception('failed', exc_info=False)
        locations = [line.split(' - ')[8].rsplit(':', 1)[0] for line in _lines(capsys)]
        assert locations == ['tests.test_logging.py:test_stat_api_and_exception_report_the_caller_location'] * 3

    def test_uses_each_loggers_own_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_logging(name='app', version='v1', environment='test')
        logging.stat(name='events', key='created')
        logging.api(action='GET', path='/', query='', response=200)
        statParts, apiParts = (line.split(' - ') for line in _lines(capsys))
        assert (statParts[1], statParts[-1]) == ('KIBA_STAT_1', 'events:created:1')
        assert (apiParts[1], apiParts[-1]) == ('KIBA_API_1', 'GET:/::200:')

    def test_request_id_is_empty_without_a_holder(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_logging(name='app', version='v1', environment='test')
        logging.info('hello')
        assert _lines(capsys)[0].split(' - ')[5] == ''

    def test_show_debug_includes_debug(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_logging(name='app', version='v1', environment='test')
        logging.debug('hidden')
        logging.init_logging(name='app', version='v1', environment='test', showDebug=True)
        logging.debug('shown')
        assert [line.split(' - ')[-1] for line in _lines(capsys)] == ['shown']


class TestJsonLogging:
    def test_writes_one_json_object_per_log_with_service_details(self, capsys: pytest.CaptureFixture[str]) -> None:
        requestIdHolder = RequestIdHolder()
        requestIdHolder.set_value(value='req-123')
        logging.init_json_logging(name='app', version='v1', environment='test', requestIdHolder=requestIdHolder)
        logging.info('hello %s', 'kiba')
        record = _json_lines(capsys)[0]
        loggedDate = datetime.datetime.strptime(str(record.pop('date')), '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=datetime.UTC)
        assert abs((datetime.datetime.now(tz=datetime.UTC) - loggedDate).total_seconds()) < 60  # noqa: PLR2004
        # NOTE(krishan711): the json formatter logs the unformatted msg, not msg % args
        assert record == {'message': 'hello %s', 'level': 'INFO', 'logger': 'root', 'format': 'KIBA_1', 'name': 'app', 'version': 'v1', 'environment': 'test', 'requestId': 'req-123'}

    def test_request_id_is_null_without_a_holder(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_json_logging(name='app', version='v1', environment='test')
        logging.info('hello')
        assert _json_lines(capsys)[0]['requestId'] is None

    def test_exceptions_log_the_traceback_as_the_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_json_logging(name='app', version='v1', environment='test')
        try:
            raise ValueError('bad value')
        except ValueError as exception:
            logging.exception(exception)
        record = _json_lines(capsys)[0]
        assert (record['level'], str(record['message']).splitlines()[0], str(record['message']).splitlines()[-1]) == ('ERROR', 'Traceback (most recent call last):', 'ValueError: bad value')

    def test_stat_fields_are_typed(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_json_logging(name='app', version='v1', environment='test')
        logging.stat(name='events', key='created', value=2.5)
        record = _json_lines(capsys)[0]
        assert {key: record[key] for key in ('format', 'message', 'statName', 'statKey', 'statValue')} == {'format': 'KIBA_STAT_1', 'message': None, 'statName': 'events', 'statKey': 'created', 'statValue': 2.5}

    def test_api_fields_are_typed_and_missing_values_are_null(self, capsys: pytest.CaptureFixture[str]) -> None:
        logging.init_json_logging(name='app', version='v1', environment='test')
        logging.api(action='GET', path='/v1/users/123', pathPattern='/v1/users/{userId}', query='limit=10', response=200, duration=0.25)
        logging.api(action='CRON', path='job', query='')
        fields = ('format', 'apiAction', 'apiPath', 'apiPathPattern', 'apiQuery', 'apiResponse', 'apiDuration')
        completeRecord, startRecord = ({key: record[key] for key in fields} for record in _json_lines(capsys))
        assert completeRecord == {'format': 'KIBA_API_1', 'apiAction': 'GET', 'apiPath': '/v1/users/123', 'apiPathPattern': '/v1/users/{userId}', 'apiQuery': 'limit=10', 'apiResponse': 200, 'apiDuration': 0.25}
        assert startRecord == {'format': 'KIBA_API_1', 'apiAction': 'CRON', 'apiPath': 'job', 'apiPathPattern': 'job', 'apiQuery': None, 'apiResponse': None, 'apiDuration': None}


class TestJsonFieldParsers:
    def test_empty_values_parse_to_none(self) -> None:
        assert (logging.json_parse_string_value(''), logging.json_parse_int_value(''), logging.json_parse_float_value('')) == (None, None, None)

    def test_values_parse_to_their_types(self) -> None:
        assert (logging.json_parse_string_value('abc'), logging.json_parse_int_value('42'), logging.json_parse_float_value('1.5')) == ('abc', 42, 1.5)
