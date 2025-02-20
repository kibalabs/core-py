import typing

from pydantic import BaseModel
from starlette.requests import Request

from core.http.basic_authentication import BasicAuthentication
from core.http.jwt import Jwt

ApiRequestDataType = typing.TypeVar('ApiRequestDataType', bound=BaseModel)  # pylint: disable=invalid-name


class KibaApiRequest(Request, typing.Generic[ApiRequestDataType]):
    data: ApiRequestDataType
    authJwt: Jwt | None = None
    authBasic: BasicAuthentication | None = None
