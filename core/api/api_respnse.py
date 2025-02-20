import typing

import orjson
from starlette.responses import JSONResponse


class KibaJSONResponse(JSONResponse):
    def render(self, content: typing.Any) -> bytes:
        return orjson.dumps(content)
