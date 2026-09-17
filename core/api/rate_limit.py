import functools
import time
import typing
from collections.abc import AsyncIterator

from pydantic import BaseModel

from core.api.api_request import KibaApiRequest
from core.api.route_metadata import RateLimitConfig
from core.api.route_metadata import update_route_metadata
from core.exceptions import InternalServerErrorException
from core.exceptions import TooManyRequestsException

_AnyReturn = typing.Awaitable[typing.Any] | AsyncIterator[typing.Any]  # type: ignore[explicit-any]
_SWEEP_INTERVAL = 1000
_MAX_ENTRY_AGE_SECONDS = 25 * 60 * 60


class _WindowConfig(typing.NamedTuple):
    label: str
    limit: int
    windowSeconds: int


class _WindowState:
    __slots__ = ('count', 'windowStart')

    def __init__(self, windowStart: float) -> None:
        self.count = 0
        self.windowStart = windowStart


_store: dict[str, dict[str, _WindowState]] = {}
_checkCount = 0


def _resolve_user_identity[ApiRequest: BaseModel](request: KibaApiRequest[ApiRequest]) -> str:
    if request.authBasic is not None:
        return request.authBasic.username
    if request.authJwt is not None:
        subject = request.authJwt.payloadDict.get('sub')
        if subject:
            return str(subject)
    raise InternalServerErrorException(message='rate_limit(keyBy="user") requires an auth decorator to run first')


def _resolve_ip_identity[ApiRequest: BaseModel](request: KibaApiRequest[ApiRequest]) -> str:
    if request.originIp is None:
        raise InternalServerErrorException(message='rate_limit(keyBy="ip") requires OriginIpMiddleware to be installed')
    return request.originIp


def _sweep_expired_entries(now: float) -> None:
    staleKeys = [storeKey for storeKey, windowStates in _store.items() if all((now - windowState.windowStart) >= _MAX_ENTRY_AGE_SECONDS for windowState in windowStates.values())]
    for storeKey in staleKeys:
        del _store[storeKey]


def rate_limit(  # type: ignore[explicit-any]
    *,
    perMinute: int | None = None,
    perFiveMinutes: int | None = None,
    perHour: int | None = None,
    perDay: int | None = None,
    keyBy: typing.Literal['user', 'ip'] = 'user',
) -> typing.Callable[[typing.Callable[[KibaApiRequest[typing.Any]], _AnyReturn]], typing.Callable[[KibaApiRequest[typing.Any]], typing.Any]]:
    windows: list[_WindowConfig] = []
    rateLimit = RateLimitConfig()
    if perMinute is not None:
        windows.append(_WindowConfig(label='perMinute', limit=perMinute, windowSeconds=60))
        rateLimit['perMinute'] = perMinute
    if perFiveMinutes is not None:
        windows.append(_WindowConfig(label='perFiveMinutes', limit=perFiveMinutes, windowSeconds=5 * 60))
        rateLimit['perFiveMinutes'] = perFiveMinutes
    if perHour is not None:
        windows.append(_WindowConfig(label='perHour', limit=perHour, windowSeconds=60 * 60))
        rateLimit['perHour'] = perHour
    if perDay is not None:
        windows.append(_WindowConfig(label='perDay', limit=perDay, windowSeconds=24 * 60 * 60))
        rateLimit['perDay'] = perDay
    if not windows:
        raise ValueError('rate_limit requires at least one of perMinute, perFiveMinutes, perHour, perDay')

    def decorator(func: typing.Callable[[KibaApiRequest[typing.Any]], _AnyReturn]) -> typing.Callable[[KibaApiRequest[typing.Any]], typing.Any]:  # type: ignore[explicit-any]
        update_route_metadata(func, {'rateLimit': rateLimit})
        routeKey = getattr(func, '__qualname__', type(func).__name__)

        @functools.wraps(func)
        async def async_wrapper(request: KibaApiRequest[typing.Any]) -> typing.Any:  # type: ignore[explicit-any, misc]
            global _checkCount  # noqa: PLW0603
            identity = _resolve_user_identity(request=request) if keyBy == 'user' else _resolve_ip_identity(request=request)
            storeKey = f'{routeKey}:{identity}'
            now = time.monotonic()
            _checkCount += 1
            if _checkCount % _SWEEP_INTERVAL == 0:
                _sweep_expired_entries(now=now)
            windowStates = _store.setdefault(storeKey, {})
            retryAfterSeconds = 0
            for window in windows:
                windowState = windowStates.get(window.label)
                if windowState is None or (now - windowState.windowStart) >= window.windowSeconds:
                    windowState = _WindowState(windowStart=now)
                    windowStates[window.label] = windowState
                if windowState.count >= window.limit:
                    remainingSeconds = window.windowSeconds - (now - windowState.windowStart)
                    retryAfterSeconds = max(retryAfterSeconds, int(remainingSeconds) + 1)
            if retryAfterSeconds > 0:
                raise TooManyRequestsException(message='RATE_LIMITED', retryAfterSeconds=retryAfterSeconds)
            for window in windows:
                windowStates[window.label].count += 1
            result = func(request)
            if hasattr(result, '__aiter__'):
                return result
            return await result

        return async_wrapper

    return decorator
