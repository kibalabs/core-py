import functools
import typing
from collections.abc import AsyncIterator
from typing import ParamSpec

from mypy_extensions import Arg
from pydantic import BaseModel
from pydantic import ValidationError
from starlette.responses import StreamingResponse

from core.api.api_request import KibaApiRequest
from core.exceptions import BadRequestException
from core.exceptions import InternalServerErrorException
from core.util import json_util
from core.util.typing_util import JsonObject

_P = ParamSpec('_P')

ApiRequest = typing.TypeVar('ApiRequest', bound=BaseModel)
ApiResponse = typing.TypeVar('ApiResponse', bound=BaseModel)


async def _convert_to_json_generator(func: AsyncIterator[ApiResponse], expectedType: typing.Type[ApiResponse]) -> AsyncIterator[bytes]:
    async for content in func:
        if not isinstance(content, expectedType):
            raise InternalServerErrorException(f'Expected response to be of type {expectedType}, got {type(content)}')
        yield json_util.dumpb(content.model_dump()) + b'\n'


def streaming_json_route(
    requestType: typing.Type[ApiRequest],
    responseType: typing.Type[ApiResponse],
) -> typing.Callable[[typing.Callable[[Arg(KibaApiRequest[ApiRequest], 'request')], AsyncIterator[ApiResponse]]], typing.Callable[_P, StreamingResponse]]:
    def decorator(func: typing.Callable[[Arg(KibaApiRequest[ApiRequest], 'request')], AsyncIterator[ApiResponse]]) -> typing.Callable[_P, StreamingResponse]:
        @functools.wraps(func)
        async def async_wrapper(*args: typing.Any) -> StreamingResponse:  # type: ignore[explicit-any, misc]
            receivedRequest = args[0]
            pathParams = receivedRequest.path_params
            queryParams = receivedRequest.query_params
            bodyBytes = await args[0].body()
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
            responseGenerator = func(request=kibaRequest)
            wrappedGenerator = _convert_to_json_generator(func=responseGenerator, expectedType=responseType)
            return StreamingResponse(content=wrappedGenerator, media_type='application/x-ndjson')

        # TODO(krishan711): figure out correct typing here
        return async_wrapper  # type: ignore[return-value]

    return decorator
