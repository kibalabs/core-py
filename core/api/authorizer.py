import functools
import typing
from collections.abc import AsyncIterator
from typing import ParamSpec

from mypy_extensions import Arg
from pydantic import BaseModel

from core import logging
from core.api.api_request import KibaApiRequest
from core.exceptions import ForbiddenException
from core.exceptions import UnauthorizedException
from core.http.basic_authentication import BasicAuthentication
from core.http.jwt import Jwt

_P = ParamSpec('_P')
_AnyReturn = typing.Awaitable[typing.Any] | AsyncIterator[typing.Any]  # type: ignore[explicit-any]


class Authorizer:
    async def validate_jwt(self, jwtString: str) -> Jwt:
        raise NotImplementedError


class SignatureAuthorizer:
    async def retrieve_signature_signer(self, signatureString: str) -> str:
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
) -> typing.Callable[[typing.Callable[[Arg(KibaApiRequest[ApiRequest], 'request')], _AnyReturn]], typing.Callable[_P, typing.Any]]:
    def decorator(func: typing.Callable[[Arg(KibaApiRequest[ApiRequest], 'request')], _AnyReturn]) -> typing.Callable[_P, typing.Any]:  # type: ignore[explicit-any]
        @functools.wraps(func)
        async def async_wrapper(request: KibaApiRequest[ApiRequest]) -> typing.Any:  # type: ignore[explicit-any, misc]
            request.authJwt = await _authorize_bearer_jwt(request=request, authorizer=authorizer)
            result = func(request=request)
            # NOTE(krishan711): this is here to support streaming responses which return an async generator
            if hasattr(result, '__aiter__'):
                return result
            return await result

        # TODO(krishan711): figure out correct typing here
        return async_wrapper  # type: ignore[return-value]

    return decorator


async def get_basic_authentication_from_authorization_signature[ApiRequest: BaseModel](request: KibaApiRequest[ApiRequest], authorizer: SignatureAuthorizer) -> BasicAuthentication:
    authorization = request.headers.get('Authorization')
    if not authorization:
        raise ForbiddenException(message='AUTH_NOT_PROVIDED')
    if not authorization.startswith('Signature '):
        raise ForbiddenException(message='AUTH_INVALID')
    signatureString = authorization.replace('Signature ', '', 1)
    try:
        signerId = await authorizer.retrieve_signature_signer(signatureString=signatureString)
    except UnauthorizedException:
        raise
    except BaseException as exception:  # noqa: BLE001
        logging.exception(exception)  # type: ignore[arg-type]
        raise ForbiddenException(message='AUTH_INVALID')
    return BasicAuthentication(username=signerId, password=signatureString)


def authorize_signature[ApiRequest: BaseModel](  # type: ignore[explicit-any]
    authorizer: SignatureAuthorizer,
) -> typing.Callable[[typing.Callable[[Arg(KibaApiRequest[ApiRequest], 'request')], _AnyReturn]], typing.Callable[_P, typing.Any]]:
    def decorator(func: typing.Callable[[Arg(KibaApiRequest[ApiRequest], 'request')], _AnyReturn]) -> typing.Callable[_P, typing.Any]:  # type: ignore[explicit-any]
        @functools.wraps(func)
        async def async_wrapper(request: KibaApiRequest[ApiRequest]) -> typing.Any:  # type: ignore[explicit-any, misc]
            request.authBasic = await get_basic_authentication_from_authorization_signature(request=request, authorizer=authorizer)
            result = func(request=request)
            # NOTE(krishan711): this is here to support streaming responses which return an async generator
            if hasattr(result, '__aiter__'):
                return result
            return await result

        # TODO(krishan711): figure out correct typing here
        return async_wrapper  # type: ignore[return-value]

    return decorator


class TokenAuthorizer:
    async def validate_token(self, token: str) -> None:
        raise NotImplementedError


class StaticTokenAuthorizer(TokenAuthorizer):
    def __init__(self, token: str) -> None:
        self._token = token

    async def validate_token(self, token: str) -> None:
        if token != self._token:
            raise ForbiddenException(message='AUTH_INVALID')


def authorize_token[ApiRequest: BaseModel](  # type: ignore[explicit-any]
    authorizer: TokenAuthorizer,
) -> typing.Callable[[typing.Callable[[Arg(KibaApiRequest[ApiRequest], 'request')], _AnyReturn]], typing.Callable[_P, typing.Any]]:
    def decorator(func: typing.Callable[[Arg(KibaApiRequest[ApiRequest], 'request')], _AnyReturn]) -> typing.Callable[_P, typing.Any]:  # type: ignore[explicit-any]
        @functools.wraps(func)
        async def async_wrapper(request: KibaApiRequest[ApiRequest]) -> typing.Any:  # type: ignore[explicit-any, misc]
            authorization = request.headers.get('Authorization')
            if not authorization:
                raise ForbiddenException(message='AUTH_NOT_PROVIDED')
            if not authorization.startswith('Token '):
                raise ForbiddenException(message='AUTH_INVALID')
            await authorizer.validate_token(authorization[6:])
            result = func(request=request)
            # NOTE(krishan711): this is here to support streaming responses which return an async generator
            if hasattr(result, '__aiter__'):
                return result
            return await result

        # TODO(krishan711): figure out correct typing here
        return async_wrapper  # type: ignore[return-value]

    return decorator
