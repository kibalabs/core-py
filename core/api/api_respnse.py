import typing

import orjson
from starlette.responses import JSONResponse


class KibaJSONResponse(JSONResponse):
    def render(self, content: typing.Any) -> bytes:  # type: ignore[explicit-any]
        return orjson.dumps(content)  # pylint: disable=no-member
