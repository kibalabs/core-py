import os
import typing
import urllib.parse as urlparse
from collections.abc import Mapping
from collections.abc import MutableMapping
from collections.abc import Sequence
from io import IOBase
from typing import IO
from typing import Any
from typing import Union

import httpx

from core import logging
from core.exceptions import HTTP_EXCEPTIONS_MAP
from core.exceptions import KibaException
from core.util import dict_util
from core.util import file_util
from core.util import json_util
from core.util.typing_util import Json

KibaResponse = httpx.Response

FileContent = Union[IO[bytes], bytes]
File = Union[FileContent, tuple[str | None, FileContent]]
HttpxFileTypes = Union[
    # file (or bytes)
    FileContent,
    # (filename, file (or bytes))
    tuple[str | None, FileContent],
    # (filename, file (or bytes), content_type)
    tuple[str | None, FileContent, str | None],
    # (filename, file (or bytes), content_type, headers)
    tuple[str | None, FileContent, str | None, Mapping[str, str]],
]
HttpxRequestFiles = Union[Mapping[str, HttpxFileTypes], Sequence[tuple[str, HttpxFileTypes]]]


class ResponseException(KibaException):
    def __init__(self, message: str | None = None, statusCode: int | None = None, headers: MutableMapping[str, str] | None = None) -> None:
        super().__init__(message=message, statusCode=statusCode, exceptionType=None)
        self.headers = headers


class Requester:
    def __init__(self, headers: Mapping[str, str] | None = None, shouldFollowRedirects: bool = True) -> None:
        self.headers = headers or {}
        self.client = httpx.AsyncClient(follow_redirects=shouldFollowRedirects)

    async def get(self, url: str, dataDict: Json | None = None, data: bytes | None = None, timeout: int | None = 10, headers: MutableMapping[str, str] | None = None, outputFilePath: str | None = None) -> KibaResponse:
        return await self.make_request(method='GET', url=url, dataDict=dataDict, data=data, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def post(self, url: str, dataDict: Json | None = None, data: bytes | None = None, timeout: int | None = 10, headers: MutableMapping[str, str] | None = None, outputFilePath: str | None = None) -> KibaResponse:
        return await self.make_request(method='POST', url=url, dataDict=dataDict, data=data, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def post_json(self, url: str, dataDict: Json | None = None, timeout: int | None = 10, headers: MutableMapping[str, str] | None = None, outputFilePath: str | None = None) -> KibaResponse:
        headers = headers or httpx.Headers()
        headers.update({'Content-Type': 'application/json'})
        return await self.make_request(method='POST', url=url, dataDict=dataDict, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def post_form(
        self,
        url: str,
        formDataDict: Mapping[str, Union[str, FileContent]] | None = None,
        formFiles: Sequence[tuple[str, HttpxFileTypes]] | None = None,
        timeout: int | None = 10,
        headers: MutableMapping[str, str] | None = None,
        outputFilePath: str | None = None,
    ) -> KibaResponse:
        headers = headers or httpx.Headers()
        # headers.update({'Content-Type': 'application/x-www-form-urlencoded'})
        return await self.make_request(method='POST', url=url, formDataDict=formDataDict, formFiles=formFiles, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def patch(self, url: str, dataDict: Json | None = None, data: bytes | None = None, timeout: int | None = 10, headers: MutableMapping[str, str] | None = None, outputFilePath: str | None = None) -> KibaResponse:
        return await self.make_request(method='PATCH', url=url, dataDict=dataDict, data=data, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def patch_json(self, url: str, dataDict: Json | None = None, timeout: int | None = 10, headers: MutableMapping[str, str] | None = None, outputFilePath: str | None = None) -> KibaResponse:
        headers = headers or httpx.Headers()
        headers.update({'Content-Type': 'application/json'})
        return await self.make_request(method='PATCH', url=url, dataDict=dataDict, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def put(self, url: str, dataDict: Json | None = None, data: bytes | None = None, timeout: int | None = 10, headers: MutableMapping[str, str] | None = None, outputFilePath: str | None = None) -> KibaResponse:
        return await self.make_request(method='PUT', url=url, dataDict=dataDict, data=data, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def put_json(self, url: str, dataDict: Json | None = None, timeout: int | None = 10, headers: MutableMapping[str, str] | None = None, outputFilePath: str | None = None) -> KibaResponse:
        headers = headers or httpx.Headers()
        headers.update({'Content-Type': 'application/json'})
        return await self.make_request(method='PUT', url=url, dataDict=dataDict, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def make_request(
        self,
        method: str,
        url: str,
        dataDict: Json | None = None,
        data: bytes | None = None,
        formDataDict: Mapping[str, Union[str, FileContent]] | None = None,
        formFiles: Sequence[tuple[str, HttpxFileTypes]] | None = None,
        timeout: int | None = 10,
        headers: MutableMapping[str, str] | None = None,
        outputFilePath: str | None = None,
    ) -> KibaResponse:
        requestHeaders = httpx.Headers({**self.headers, **(headers or {})})
        # TODO(krishan711): rename parameter to content when ready
        contentDict = dataDict
        content = data
        if contentDict is not None:
            if content is not None:
                logging.error('Error: contentDict and content should never both be provided to make_request. content will be overwritten by contentDict.')
            if method == 'GET':
                urlParts = urlparse.urlparse(url)
                currentQuery = urlparse.parse_qs(urlParts.query)
                queryString = urlparse.urlencode(query=dict_util.merge_dicts(currentQuery, typing.cast(dict[str, str], contentDict)), doseq=True)
                url = urlparse.urlunsplit(components=(urlParts.scheme, urlParts.netloc, urlParts.path, queryString, urlParts.fragment))
            if method in {'POST', 'PUT', 'PATCH'}:
                # TODO(krishan711): this should only happen if json is in the content headers
                # if requestHeaders.get('content-type') and requestHeaders.get('content-type').lower() == 'application/json':
                content = json_util.dumps(contentDict).encode()
        files: list[tuple[str, HttpxFileTypes]] | None = None
        innerData: dict[Any, Any] | None = None  # type: ignore[explicit-any]
        if formDataDict:
            if method == 'POST':
                formDataDictCleaned: dict[str, str] = {}
                files = []
                for name, value in formDataDict.items():
                    if isinstance(value, IO | bytes | IOBase):
                        files.append((name, value))
                    else:
                        formDataDictCleaned[name] = value
                innerData = formDataDictCleaned
            else:
                logging.error('Error: formDataDict should only be passed into POST requests.')
        if formFiles:
            if method == 'POST':
                files = files or []
                files += formFiles
            else:
                logging.error('Error: formFiles should only be passed into POST requests.')
        request = self.client.build_request(method=method, url=url, content=content, data=innerData, files=files, timeout=timeout, headers=requestHeaders)
        httpxResponse = await self.client.send(request=request)
        if 400 <= httpxResponse.status_code < 600:  # noqa: PLR2004
            message = httpxResponse.text
            if not message and httpxResponse.status_code == 401 and httpxResponse.headers.get('www-authenticate'):  # noqa: PLR2004
                message = httpxResponse.headers['www-authenticate']
            if HTTP_EXCEPTIONS_MAP.get(httpxResponse.status_code) is not None:
                exceptionCls = HTTP_EXCEPTIONS_MAP[httpxResponse.status_code]
                exception: KibaException = exceptionCls(message=message)
            else:
                exception = ResponseException(message=message, statusCode=httpxResponse.status_code, headers=httpxResponse.headers)
            raise exception
        # TODO(krishan711): this would be more efficient if streamed
        if outputFilePath is not None:
            if os.path.dirname(outputFilePath):
                os.makedirs(os.path.dirname(outputFilePath), exist_ok=True)
            await file_util.write_file_bytes(filePath=outputFilePath, content=httpxResponse.content)
        return httpxResponse

    async def close_connections(self) -> None:
        await self.client.aclose()
