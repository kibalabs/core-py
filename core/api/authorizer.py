# import inspect
import functools
import sys
import typing

from mypy_extensions import Arg
from pydantic import BaseModel

from core.api.api_request import KibaApiRequest
from core.exceptions import ForbiddenException
from core.http.jwt import Jwt

if sys.version_info >= (3, 10):  # pragma: no cover
    from typing import ParamSpec
else:  # pragma: no cover
    from typing_extensions import ParamSpec

_P = ParamSpec("_P")


class Authorizer:
    async def validate_jwt(self, jwtString: str) -> Jwt:
        raise NotImplementedError()


ApiRequest = typing.TypeVar("ApiRequest", bound=BaseModel)


def authorize_bearer_jwt(  # type: ignore[misc]
    authorizer: Authorizer,
) -> typing.Callable[[typing.Callable[[Arg(KibaApiRequest[ApiRequest], 'request')], typing.Awaitable[typing.Any]]], typing.Callable[_P, typing.Any]]:
    def decorator(func: typing.Callable[[Arg(KibaApiRequest[ApiRequest], 'request')], typing.Awaitable[typing.Any]]) -> typing.Callable[_P, typing.Any]:  # type: ignore[misc]
        @functools.wraps(func)
        async def async_wrapper(request: KibaApiRequest[ApiRequest]) -> typing.Any:  # type: ignore[misc]
            authorization = request.headers.get('Authorization')
            if not authorization:
                raise ForbiddenException(message='AUTH_NOT_PROVIDED')
            if not authorization.startswith('Bearer '):
                raise ForbiddenException(message='AUTH_INVALID')
            jwtString = authorization.replace('Bearer ', '')
            try:
                jwt = await authorizer.validate_jwt(jwtString=jwtString)
            except BaseException:
                raise ForbiddenException(message='AUTH_INVALID')
            request.authJwt = jwt
            return await func(request=request)
        # TODO(krishan711): figure out correct typing here
        return async_wrapper  # type: ignore[return-value]
    return decorator
