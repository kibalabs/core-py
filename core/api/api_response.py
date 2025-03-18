import typing

from starlette.responses import JSONResponse

from core.util import json_util


class KibaJSONResponse(JSONResponse):
    def render(self, content: typing.Any) -> bytes:  # type: ignore[explicit-any]
        return json_util.dumpb(content)
