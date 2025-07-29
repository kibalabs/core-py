import functools
import typing
from typing import ParamSpec

from mypy_extensions import Arg
from pydantic import BaseModel

from core.api.api_request import KibaApiRequest
from core.exceptions import ForbiddenException
from core.http.jwt import Jwt

_P = ParamSpec('_P')


class Authorizer:
    async def validate_jwt(self, jwtString: str) -> Jwt:
        raise NotImplementedError


async def _authorize_bearer_jwt[ApiRequest: BaseModel](request: KibaApiRequest[ApiRequest], authorizer: Authorizer) -> Jwt:
    authorization = request.headers.get('Authorization')
    if not authorization:
        raise ForbiddenException(message='AUTH_NOT_PROVIDED')
    if not authorization.startswith('Bearer '):
        raise ForbiddenException(message='AUTH_INVALID')
    jwtString = authorization.replace('Bearer ', '')
    try:
        jwt = await authorizer.validate_jwt(jwtString=jwtString)
    except BaseException:  # noqa: BLE001
        raise ForbiddenException(message='AUTH_INVALID')
    return jwt


def authorize_bearer_jwt[ApiRequest: BaseModel](  # type: ignore[explicit-any]
    authorizer: Authorizer,
) -> typing.Callable[[typing.Callable[[Arg(KibaApiRequest[ApiRequest], 'request')], typing.Awaitable[typing.Any]]], typing.Callable[_P, typing.Any]]:
    def decorator(func: typing.Callable[[Arg(KibaApiRequest[ApiRequest], 'request')], typing.Awaitable[typing.Any]]) -> typing.Callable[_P, typing.Any]:  # type: ignore[explicit-any]
        @functools.wraps(func)
        async def async_wrapper(request: KibaApiRequest[ApiRequest]) -> typing.Any:  # type: ignore[explicit-any, misc]
            request.authJwt = await _authorize_bearer_jwt(request=request, authorizer=authorizer)
            return await func(request=request)

        # TODO(krishan711): figure out correct typing here
        return async_wrapper  # type: ignore[return-value]

    return decorator
