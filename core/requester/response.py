from __future__ import annotations

import datetime
import json
import typing

import httpx
from pydantic import BaseModel

from core.util import date_util


class KibaResponse(BaseModel):
    status: int
    date: datetime.datetime
    headers: dict[str, str]
    content: bytes

    @classmethod
    def from_httpx_response(cls, httpxResponse: httpx.Response) -> KibaResponse:
        return cls(
            status=httpxResponse.status_code,
            date=date_util.datetime_from_now(),
            headers=dict(httpxResponse.headers),
            content=httpxResponse.content,
        )

    def json(self) -> typing.Any:  # type: ignore[explicit-any, override]
        return json.loads(self.content)
