from pydantic import BaseModel
from starlette.requests import Request

from core.http.basic_authentication import BasicAuthentication
from core.http.jwt import Jwt


class KibaApiRequest[ApiRequestDataType: BaseModel](Request):
    data: ApiRequestDataType
    authJwt: Jwt | None = None
    authBasic: BasicAuthentication | None = None
