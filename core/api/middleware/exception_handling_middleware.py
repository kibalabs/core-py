from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.responses import Response

from core import logging
from core.exceptions import KibaException
from core.exceptions import RedirectException


class ExceptionHandlingMiddleware(BaseHTTPMiddleware):

    @staticmethod
    def _convert_exception(exception: KibaException) -> Response:
        response = JSONResponse(status_code=exception.statusCode, content=exception.to_dict())
        return response

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            response = await call_next(request)
        except RedirectException as exception:
            response = Response(status_code=exception.statusCode)
            response.headers['Location'] = exception.location
            # TODO(krishan711): clean this up after major version bump (since shouldAddCacheHeader field will always exist)
            if not hasattr(exception, 'shouldAddCacheHeader') or exception.shouldAddCacheHeader:
                response.headers['Cache-Control'] = f'max-age={60 * 60 * 24 * 365}'
        except KibaException as exception:
            logging.exception(exception)
            response = self._convert_exception(exception=exception)
        except RequestValidationError as exception:
            logging.exception(exception)
            response = self._convert_exception(exception=KibaException(message=str(exception).replace('\n', ' '), statusCode=400, exceptionType=exception.__class__.__name__))
        except Exception as exception:  # pylint: disable=broad-except
            logging.exception(exception)
            response = self._convert_exception(exception=KibaException.from_exception(exception=exception))
        return response
