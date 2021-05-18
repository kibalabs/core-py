import logging
import os
import time
import uuid
from typing import Callable

from fastapi.routing import APIRoute
from fastapi.requests import Request
from fastapi.responses import Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from core.exceptions import KibaException


class KibaRoute(APIRoute):

    @staticmethod
    def _convert_exception(exception: KibaException) -> Response:
        response = JSONResponse(status_code=exception.statusCode, content=exception.to_dict())
        return response

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()  # pylint: disable=invalid-name
        async def custom_route_handler(request: Request) -> Response:
            requestId = str(uuid.uuid4()).replace('-', '')
            startTime = time.time()
            logging.info(f'{requestId} - {request.method} - {request.url.path}')
            try:
                response = await original_route_handler(request)
            except KibaException as exception:
                logging.exception(exception)
                response = self._convert_exception(exception=exception)
            except RequestValidationError as exception:
                logging.exception(exception)
                response = self._convert_exception(exception=KibaException(message=str(exception).replace('\n', ' '), statusCode=400, exceptionType=exception.__class__.__name__))
            except Exception as exception:  # pylint: disable=broad-except
                logging.exception(exception)
                response = self._convert_exception(exception=KibaException.from_exception(exception=exception))
            duration = time.time() - startTime
            response.headers['X-Response-Time'] = str(duration)
            response.headers['X-Server'] = os.environ.get('NAME', '')
            response.headers['X-Server-Version'] = os.environ.get('VERSION', '')
            logging.info(f'{requestId} - {request.method} - {request.url.path} - {response.status_code} - {duration}')
            return response
        return custom_route_handler
