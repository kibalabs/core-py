import typing
from collections.abc import Mapping

from starlette.datastructures import UploadFile
from starlette.requests import Request

from core.api.uploaded_file import UploadedFile
from core.exceptions import BadRequestException
from core.util import json_util
from core.util.typing_util import JsonObject


async def read_request_body(request: Request) -> Mapping[str, object]:
    if request.headers.get('Content-Type', '').startswith('multipart/form-data'):
        body: dict[str, object] = {}
        # NOTE(krishan711): the form is closed on exit so uploaded files' temporary files are closed (their content has been read by then)
        async with request.form() as form:
            for key, value in form.multi_items():
                if key in body:
                    raise BadRequestException(f'Invalid form body: {key} is given more than once')
                body[key] = UploadedFile(filename=value.filename, contentType=value.content_type, content=await value.read()) if isinstance(value, UploadFile) else value
        return body
    bodyBytes = await request.body()
    if len(bodyBytes) == 0:
        return {}
    try:
        jsonBody = typing.cast(JsonObject, json_util.loads(bodyBytes.decode()))
    except json_util.JsonDecodeException as exception:
        raise BadRequestException(f'Invalid JSON body: {exception}')
    if not isinstance(jsonBody, dict):
        raise BadRequestException('Invalid JSON body: expected an object')
    return jsonBody
