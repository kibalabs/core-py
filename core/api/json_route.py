import functools
import typing

from pydantic import BaseModel
from pydantic import ValidationError
from starlette.requests import Request

from core.api.api_request import KibaApiRequest
from core.api.api_response import KibaJSONResponse
from core.exceptions import BadRequestException
from core.exceptions import InternalServerErrorException
from core.util import json_util
from core.util.typing_util import JsonObject


def json_route[ApiRequest: BaseModel, ApiResponse: BaseModel](
    requestType: typing.Type[ApiRequest],
    responseType: typing.Type[ApiResponse],
) -> typing.Callable[[typing.Callable[[KibaApiRequest[ApiRequest]], typing.Awaitable[ApiResponse]]], typing.Callable[[Request], typing.Awaitable[KibaJSONResponse]]]:
    def decorator(func: typing.Callable[[KibaApiRequest[ApiRequest]], typing.Awaitable[ApiResponse]]) -> typing.Callable[[Request], typing.Awaitable[KibaJSONResponse]]:
        @functools.wraps(func)
        async def async_wrapper(receivedRequest: Request) -> KibaJSONResponse:
            pathParams = receivedRequest.path_params
            queryParams = receivedRequest.query_params
            bodyBytes = await receivedRequest.body()
            if len(bodyBytes) == 0:
                body: JsonObject = {}
            else:
                try:
                    body = typing.cast(JsonObject, json_util.loads(bodyBytes.decode()))
                except json_util.JsonDecodeException as exception:
                    raise BadRequestException(f'Invalid JSON body: {exception}')
            allParams = {**pathParams, **body, **queryParams}
            try:
                requestParams = requestType(**allParams)
            except ValidationError as exception:
                validationErrorMessage = ', '.join([f'{".".join([str(value) for value in error["loc"]])}: {error["msg"]}' for error in exception.errors()])
                raise BadRequestException(f'Invalid request: {validationErrorMessage}')
            kibaRequest: KibaApiRequest[ApiRequest] = KibaApiRequest(scope=receivedRequest.scope, receive=receivedRequest._receive, send=receivedRequest._send)  # noqa: SLF001
            kibaRequest.data = requestParams
            receivedResponse = await func(kibaRequest)
            if not isinstance(receivedResponse, responseType):
                raise InternalServerErrorException(f'Expected response to be of type {responseType}, got {type(receivedResponse)}')
            return KibaJSONResponse(content=receivedResponse.model_dump())

        return async_wrapper

    return decorator
