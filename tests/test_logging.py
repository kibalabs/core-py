import logging as pythonLogging
from collections.abc import Iterator

import pytest

from core import logging

APP_LOGGER_NAME = 'test-app-library'


@pytest.fixture(autouse=True)
def restore_logger_levels() -> Iterator[None]:
    loggerNames = [*logging.DEFAULT_EXTERNAL_LOGGER_NAMES, APP_LOGGER_NAME]
    originalLevels = {loggerName: pythonLogging.getLogger(loggerName).level for loggerName in loggerNames}
    for loggerName in loggerNames:
        pythonLogging.getLogger(loggerName).setLevel(pythonLogging.NOTSET)
    yield
    for loggerName, level in originalLevels.items():
        pythonLogging.getLogger(loggerName).setLevel(level)


def _levels(loggerNames: list[str]) -> list[int]:
    return [pythonLogging.getLogger(loggerName).level for loggerName in loggerNames]


def test_init_quietens_core_external_loggers_by_default() -> None:
    logging.init_basic_logging()

    assert _levels(['httpx2', 'sqlalchemy', APP_LOGGER_NAME]) == [pythonLogging.WARNING, pythonLogging.WARNING, pythonLogging.NOTSET]


def test_extra_logger_names_are_added_to_the_defaults() -> None:
    logging.init_basic_logging(extraLoggerNames=[APP_LOGGER_NAME])

    assert _levels(['httpx2', APP_LOGGER_NAME]) == [pythonLogging.WARNING, pythonLogging.WARNING]


def test_logger_names_replace_the_defaults() -> None:
    logging.init_basic_logging(loggerNames=[APP_LOGGER_NAME])

    assert _levels(['httpx2', APP_LOGGER_NAME]) == [pythonLogging.NOTSET, pythonLogging.WARNING]
