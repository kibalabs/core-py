import dataclasses
import json
import logging
import os
import re
import sys
import typing
from logging import Formatter
from logging import Logger
from logging import LogRecord
from logging import StreamHandler
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

from core.util.typing_util import JSON
from core.util.value_holder import RequestIdHolder


@dataclasses.dataclass
class LogFormat:
    loggerType: str
    loggerName: str
    loggerFormat: str
    fieldNames: List[str]


_LOGGING_FORMAT_VERSION = 1
ROOT_FORMAT = LogFormat(loggerType="", loggerName=f"KIBA_{_LOGGING_FORMAT_VERSION}", loggerFormat="%(message)s", fieldNames=[])
STAT_FORMAT = LogFormat(loggerType="stat", loggerName=f"KIBA_STAT_{_LOGGING_FORMAT_VERSION}", loggerFormat="%(statName)s:%(statKey)s:%(statValue)s", fieldNames=['statName', 'statKey', 'statValue'])
API_FORMAT = LogFormat(loggerType="api", loggerName=f"KIBA_API_{_LOGGING_FORMAT_VERSION}", loggerFormat="%(apiAction)s:%(apiPath)s:%(apiQuery)s:%(apiResponse)s:%(apiDuration)s", fieldNames=['apiAction', 'apiPath', 'apiQuery', 'apiResponse', 'apiDuration'])
ALL_LOGGER_FORMATS = [ROOT_FORMAT, STAT_FORMAT, API_FORMAT]

ROOT_LOGGER = logging.getLogger(ROOT_FORMAT.loggerType)
STAT_LOGGER = logging.getLogger(STAT_FORMAT.loggerType)
API_LOGGER = logging.getLogger(API_FORMAT.loggerType)


class KibaLoggingFormatter(Formatter):

    _BASE_FORMAT_STRING = '%(asctime)s - {format} - {name} - {version} - {environment} - %(requestId)s - %(levelname)s - %(name)s - %(pathname)s:%(funcName)s:%(lineno)s - {logMessage}'

    def __init__(self, logFormat: LogFormat, name: str, version: str, environment: str, requestIdHolder: Optional[RequestIdHolder]) -> None:
        formatString = self._BASE_FORMAT_STRING.format(format=logFormat.loggerName, name=name, version=version, environment=environment, logMessage=logFormat.loggerFormat)
        super().__init__(fmt=formatString)
        self.logFormat = logFormat
        self.name = name
        self.version = version
        self.environment = environment
        self.requestIdHolder = requestIdHolder

    def format(self, record: LogRecord) -> str:
        record.pathname = re.sub(os.getcwd() + '.', '', record.pathname).replace('/', '.')
        setattr(record, 'requestId', self.requestIdHolder.get_value() if self.requestIdHolder is not None else '')
        return super().format(record=record)


class KibaJsonLoggingFormatter(KibaLoggingFormatter):

    def format(self, record: LogRecord) -> str:
        message = self.formatException(record.exc_info) if record.exc_info else str(record.msg)
        recordDict = {
            'dateMillis': int(record.created * 1000),
            'path': record.pathname,
            'function': record.funcName,
            'line': record.lineno,
            'message': message,
            'level': record.levelname,
            'logger': record.name,
            'format': self.logFormat.loggerName,
            'name': self.name,
            'version': self.version,
            'environment': self.environment,
            'requestId': self.requestIdHolder.get_value() if self.requestIdHolder is not None else '',
        }
        for fieldName in self.logFormat.fieldNames:
            recordDict[fieldName] = record.__dict__[fieldName]
        return json.dumps(recordDict)


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


def init_json_logging(name: str, version: str, environment: str, showDebug: bool = False, requestIdHolder: Optional[RequestIdHolder] = None) -> None:
    loggingLevel = logging.DEBUG if showDebug else logging.INFO
    for logFormat in ALL_LOGGER_FORMATS:
        logger = logging.getLogger(name=logFormat.loggerType)
        handler = StreamHandler(stream=sys.stdout)
        handler.setFormatter(fmt=KibaJsonLoggingFormatter(logFormat=logFormat, name=name, version=version, environment=environment, requestIdHolder=requestIdHolder))
        init_logger(logger=logger, loggingLevel=loggingLevel, handler=handler)


def init_basic_logging(showDebug: bool = False) -> None:
    loggingLevel = logging.DEBUG if showDebug else logging.INFO
    for logFormat in ALL_LOGGER_FORMATS:
        logger = logging.getLogger(name=logFormat.loggerType)
        handler = StreamHandler(stream=sys.stdout)
        handler.setFormatter(fmt=Formatter(fmt=logFormat.loggerFormat))
        init_logger(logger=logger, loggingLevel=loggingLevel, handler=handler)


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
        STAT_LOGGER.log(level=logging.INFO, msg='', extra=typing.cast(Dict[str, str], {'statName': nameValue, 'statKey': keyValue, 'statValue': statValue}))


def api(action: str, path: str, query: str, response: Optional[int] = None, duration: Optional[float] = None) -> None:
    if API_LOGGER.isEnabledFor(level=logging.INFO):
        actionString = _serialize_string_value(value=action)
        pathString = _serialize_string_value(value=path)
        queryString = _serialize_string_value(value=query)
        responseString = _serialize_numeric_value(value=response)
        durationString = _serialize_numeric_value(value=duration)
        API_LOGGER.log(level=logging.INFO, msg='', extra=typing.cast(Dict[str, str], {'apiAction': actionString, 'apiPath': pathString, 'apiQuery': queryString, 'apiResponse': responseString or '', 'apiDuration': durationString or ''}))


# Wrappers around common python logging functions which go straight to the root logger

CRITICAL = logging.CRITICAL
ERROR = logging.ERROR
ERROR = logging.ERROR
WARNING = logging.WARNING
INFO = logging.INFO
DEBUG = logging.DEBUG


def _log(level: int, msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
    if ROOT_LOGGER.isEnabledFor(level=level):
        ROOT_LOGGER._log(level=level, msg=msg, args=args, **kwargs)  # type: ignore[attr-defined, misc]  # pylint: disable=protected-access


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
