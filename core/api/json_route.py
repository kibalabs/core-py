import functools
import json
import typing
from typing import ParamSpec

from mypy_extensions import Arg
from pydantic import BaseModel
from pydantic import ValidationError

from core.api.api_request import KibaApiRequest
from core.api.api_respnse import KibaJSONResponse
from core.exceptions import BadRequestException
from core.exceptions import InternalServerErrorException

_P = ParamSpec('_P')

ApiRequest = typing.TypeVar('ApiRequest', bound=BaseModel)
ApiResponse = typing.TypeVar('ApiResponse', bound=BaseModel)


def json_route(
    requestType: typing.Type[ApiRequest],
    responseType: typing.Type[ApiResponse],
) -> typing.Callable[[typing.Callable[[Arg(KibaApiRequest[ApiRequest], 'request')], typing.Awaitable[ApiResponse]]], typing.Callable[_P, KibaJSONResponse]]:
    def decorator(func: typing.Callable[[Arg(KibaApiRequest[ApiRequest], 'request')], typing.Awaitable[ApiResponse]]) -> typing.Callable[_P, KibaJSONResponse]:
        @functools.wraps(func)
        async def async_wrapper(*args: typing.Any) -> KibaJSONResponse:  # type: ignore[explicit-any, misc]
            receivedRequest = args[0]
            pathParams = receivedRequest.path_params
            # TODO(krishan711): move these to get request only
            queryParams = receivedRequest.query_params
            bodyBytes = await args[0].body()
            if len(bodyBytes) == 0:
                body = {}
            else:
                try:
                    body = json.loads(bodyBytes.decode())
                except json.JSONDecodeError as exception:
                    raise BadRequestException(f'Invalid JSON body: {exception}')
            allParams = {**pathParams, **body, **queryParams}
            try:
                requestParams = requestType(**allParams)
            except ValidationError as exception:
                validationErrorMessage = ', '.join([f'{".".join([str(value) for value in error["loc"]])}: {error["msg"]}' for error in exception.errors()])
                raise BadRequestException(f'Invalid request: {validationErrorMessage}')
            kibaRequest: KibaApiRequest[ApiRequest] = KibaApiRequest(scope=receivedRequest.scope, receive=receivedRequest._receive, send=receivedRequest._send)  # noqa: SLF001
            kibaRequest.data = requestParams
            receivedResponse = await func(request=kibaRequest)
            if not isinstance(receivedResponse, responseType):
                raise InternalServerErrorException(f'Expected response to be of type {responseType}, got {type(receivedResponse)}')
            return KibaJSONResponse(content=receivedResponse.model_dump())

        # TODO(krishan711): figure out correct typing here
        return async_wrapper  # type: ignore[return-value]

    return decorator
