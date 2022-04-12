import logging
import os
import re
import sys
from logging import Formatter, LogRecord
from logging import Logger
from logging import StreamHandler
from typing import Any, Dict, Optional
from typing import Union
import dataclasses
import typing

from core.util.typing_util import JSON
from core.util.value_holder import RequestIdHolder


@dataclasses.dataclass
class LogFormat:
    loggerType: str
    loggerName: str
    loggerFormat: str


_LOGGING_FORMAT_VERSION = 1
ROOT_FORMAT = LogFormat(loggerType="", loggerName=f"KIBA_{_LOGGING_FORMAT_VERSION}", loggerFormat="%(message)s")
STAT_FORMAT = LogFormat(loggerType="stat", loggerName=f"KIBA_STAT_{_LOGGING_FORMAT_VERSION}", loggerFormat="%(name)s:%(key)s:%(value)s")
API_FORMAT = LogFormat(loggerType="api", loggerName=f"KIBA_API_{_LOGGING_FORMAT_VERSION}", loggerFormat="%(action)s:%(path)s:%(query)s:%(response)s:%(duration)s")
ALL_LOGGER_FORMATS = [ROOT_FORMAT, STAT_FORMAT, API_FORMAT]

ROOT_LOGGER = logging.getLogger(ROOT_FORMAT.loggerType)
STAT_LOGGER = logging.getLogger(STAT_FORMAT.loggerType)
API_LOGGER = logging.getLogger(API_FORMAT.loggerType)


class KibaLoggingFormatter(Formatter):

    _BASE_FORMAT_STRING = '%(asctime)s - {format} - {name} - {version} - {environment} - %(requestId)s - %(levelname)s - %(name)s - %(pathname)s:%(funcName)s:%(lineno)s - {logMessage}'

    def __init__(self, logFormat: LogFormat, name: str, version: str, environment: str, requestIdHolder: Optional[RequestIdHolder]) -> None:
        formatString = self._BASE_FORMAT_STRING.format(format=logFormat.loggerName, name=name, version=version, environment=environment, logMessage=logFormat.loggerFormat)
        super().__init__(fmt=formatString)
        self.requestIdHolder = requestIdHolder

    def format(self, record: LogRecord) -> str:
        record.pathname = re.sub(os.getcwd() + '.', '', record.pathname).replace('/', '.')
        setattr(record, 'requestId', self.requestIdHolder.get_value() if self.requestIdHolder is not None else '')
        return super().format(record=record)


def init_logger(logger: Logger, loggingLevel: int, handler: StreamHandler) -> None:
    logger.propagate = False
    logger.handlers = [handler]
    logger.setLevel(level=loggingLevel)


def init_logging(name: str, version: str, environment: str, showDebug: bool = False, requestIdHolder: Optional[RequestIdHolder] = None) -> None:
    loggingLevel = logging.DEBUG if showDebug else logging.INFO
    for logFormat in ALL_LOGGER_FORMATS:
        logger = logging.getLogger(name=logFormat.loggerType)
        handler = StreamHandler(stream=sys.stdout)
        handler.setFormatter(fmt=KibaLoggingFormatter(logFormat=logFormat, name=name, version=version, environment=environment, requestIdHolder=requestIdHolder))
        init_logger(logger=logger, loggingLevel=loggingLevel, handler=handler)


def init_basic_logging(showDebug: bool = False) -> None:
    loggingLevel = logging.DEBUG if showDebug else logging.INFO
    for logFormat in ALL_LOGGER_FORMATS:
        logger = logging.getLogger(name=logFormat.loggerType)
        handler = StreamHandler(stream=sys.stdout)
        handler.setFormatter(fmt=Formatter(fmt=logFormat.loggerFormat))
        init_logger(logger=logger, loggingLevel=loggingLevel, handler=handler)


# Wrappers around common python logging functions which go straight to the root logger
def _log(level: int, msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
    if ROOT_LOGGER.isEnabledFor(level=level):
        ROOT_LOGGER._log(level=level, msg=msg, args=args, **kwargs)  # type: ignore[attr-defined, misc]  # pylint: disable=protected-access


CRITICAL = logging.CRITICAL
ERROR = logging.ERROR
ERROR = logging.ERROR
WARNING = logging.WARNING
INFO = logging.INFO
DEBUG = logging.DEBUG


def critical(msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
    _log(level=CRITICAL, msg=msg, *args, **kwargs)  # type: ignore[misc]


def error(msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
    _log(level=ERROR, msg=msg, *args, **kwargs)  # type: ignore[misc]


def exception(msg: str, *args: Any, exc_info: bool = True, **kwargs: Any) -> None:  # type: ignore[misc]  # pylint: disable=invalid-name
    _log(level=ERROR, msg=msg, exc_info=exc_info, *args, **kwargs)  # type: ignore[misc]


def warning(msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
    _log(level=WARNING, msg=msg, *args, **kwargs)  # type: ignore[misc]


def info(msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
    _log(level=INFO, msg=msg, *args, **kwargs)  # type: ignore[misc]


def debug(msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
    _log(level=DEBUG, msg=msg, *args, **kwargs)  # type: ignore[misc]


def basicConfig(**kwargs: JSON) -> None:  # pylint: disable=invalid-name
    logging.basicConfig(**kwargs)


def getLogger(name: str = Optional[None]) -> Logger:  # pylint: disable=invalid-name
    return logging.getLogger(name=name)


def _serialize_numeric_value(value: Union[None, float, int]) -> str:
    if value is None or value == '':  # type: ignore[comparison-overlap]
        return ''
    roundedNumber = round(value, 6)
    return f'{roundedNumber:f}'.rstrip('0').rstrip('.')


def _serialize_string_value(value: str) -> str:
    return value.replace(':', '__')


def stat(name: str, key: str, value: float) -> None:
    if STAT_LOGGER.isEnabledFor(level=logging.INFO):
        nameValue = _serialize_string_value(value=str(name))
        keyValue = _serialize_string_value(value=str(key))
        statValue = _serialize_numeric_value(value=value)
        STAT_LOGGER.log(level=logging.INFO, msg='', extra=typing.cast(Dict[str, str], {'name': nameValue, 'key': keyValue, 'value': statValue}))  # pylint: disable=protected-access


def api(action: str, path: str, query: str, response: Optional[int] = None, duration: Optional[float] = None) -> None:
    if API_LOGGER.isEnabledFor(level=logging.INFO):
        actionString = _serialize_string_value(value=action)
        pathString = _serialize_string_value(value=path)
        queryString = _serialize_string_value(value=query)
        responseString = _serialize_numeric_value(value=response)
        durationString = _serialize_numeric_value(value=duration)
        API_LOGGER.log(level=logging.INFO, msg='', extra=typing.cast(Dict[str, str], {'action': actionString, 'path': pathString, 'query': queryString, 'response': responseString or '', 'duration': durationString or ''}))  # pylint: disable=protected-access
