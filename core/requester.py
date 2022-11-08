import json
import os
import typing
import urllib.parse as urlparse
from io import IOBase
from typing import IO
from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import MutableMapping
from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import Union

import httpx

from core import logging
from core.exceptions import HTTP_EXCEPTIONS_MAP
from core.exceptions import KibaException
from core.util import dict_util
from core.util import file_util
from core.util.typing_util import JSON

KibaResponse = httpx.Response

FileContent = Union[IO[bytes], bytes]
File = Union[FileContent, Tuple[Optional[str], FileContent]]
HttpxFileTypes = Union[
    # file (or bytes)
    FileContent,
    # (filename, file (or bytes))
    Tuple[Optional[str], FileContent],
    # (filename, file (or bytes), content_type)
    Tuple[Optional[str], FileContent, Optional[str]],
    # (filename, file (or bytes), content_type, headers)
    Tuple[Optional[str], FileContent, Optional[str], Mapping[str, str]],
]
HttpxRequestFiles = Union[Mapping[str, HttpxFileTypes], Sequence[Tuple[str, HttpxFileTypes]]]


class ResponseException(KibaException):

    def __init__(self, message: Optional[str] = None, statusCode: Optional[int] = None, headers: Optional[MutableMapping[str, str]] = None) -> None:
        super().__init__(message=message, statusCode=statusCode, exceptionType=None)
        self.headers = headers


class Requester:

    def __init__(self, headers: Optional[Mapping[str, str]] = None, shouldFollowRedirects: bool = True):
        self.headers = headers or {}
        self.client = httpx.AsyncClient(follow_redirects=shouldFollowRedirects)

    async def get(self, url: str, dataDict: Optional[JSON] = None, data: Optional[bytes] = None, timeout: Optional[int] = 10, headers: Optional[MutableMapping[str, str]] = None, outputFilePath: Optional[str] = None) -> KibaResponse:
        return await self.make_request(method='GET', url=url, dataDict=dataDict, data=data, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def post(self, url: str, dataDict: Optional[JSON] = None, data: Optional[bytes] = None, timeout: Optional[int] = 10, headers: Optional[MutableMapping[str, str]] = None, outputFilePath: Optional[str] = None) -> KibaResponse:
        return await self.make_request(method='POST', url=url, dataDict=dataDict, data=data, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def post_json(self, url: str, dataDict: Optional[JSON] = None, timeout: Optional[int] = 10, headers: Optional[MutableMapping[str, str]] = None, outputFilePath: Optional[str] = None) -> KibaResponse:
        headers = headers or httpx.Headers()
        headers.update({'Content-Type': 'application/json'})
        return await self.make_request(method='POST', url=url, dataDict=dataDict, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def post_form(self, url: str, formDataDict: Optional[Mapping[str, Union[str, FileContent]]] = None, formFiles: Optional[Sequence[Tuple[str, HttpxFileTypes]]] = None, timeout: Optional[int] = 10, headers: Optional[MutableMapping[str, str]] = None, outputFilePath: Optional[str] = None) -> KibaResponse:
        headers = headers or httpx.Headers()
        # headers.update({'Content-Type': 'application/x-www-form-urlencoded'})
        return await self.make_request(method='POST', url=url, formDataDict=formDataDict, formFiles=formFiles, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def make_request(self, method: str, url: str, dataDict: Optional[JSON] = None, data: Optional[bytes] = None, formDataDict: Optional[Mapping[str, Union[str, FileContent]]] = None, formFiles: Optional[Sequence[Tuple[str, HttpxFileTypes]]] = None, timeout: Optional[int] = 10, headers: Optional[MutableMapping[str, str]] = None, outputFilePath: Optional[str] = None) -> KibaResponse:
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
                queryString = urlparse.urlencode(query=dict_util.merge_dicts(currentQuery, typing.cast(Dict[str, str], contentDict)), doseq=True)  # type: ignore[arg-type]
                url = urlparse.urlunsplit(components=(urlParts.scheme, urlParts.netloc, urlParts.path, queryString, urlParts.fragment))
            if method == 'POST':
                # TODO(krishan711): this should only happen if json is in the content headers
                # if requestHeaders.get('content-type') and requestHeaders.get('content-type').lower() == 'application/json':
                content = json.dumps(contentDict).encode()
        files: Optional[List[Tuple[str, HttpxFileTypes]]] = None
        innerData: Optional[Dict[Any, Any]] = None  # type: ignore[misc]
        if formDataDict:
            if method == 'POST':
                formDataDictCleaned: Dict[str, str] = {}
                files = []
                for name, value in formDataDict.items():
                    if isinstance(value, (IO, bytes, IOBase)):
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
        if 400 <= httpxResponse.status_code < 600:
            message = httpxResponse.text
            if not message and httpxResponse.status_code == 401 and httpxResponse.headers.get('www-authenticate'):
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
