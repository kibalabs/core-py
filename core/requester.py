import os
import json
from io import IOBase
from typing import IO, List, Mapping, Optional, Union
from typing import Dict
import urllib.parse as urlparse
import logging

import httpx

from core.util import file_util
from core.util import dict_util
from core.util.typing_util import JSON

KibaResponse = httpx.Response

FileContent = Union[IO[str], IO[bytes], str, bytes]

class ResponseException(Exception):

    def __init__(self, message: Optional[str] = None, statusCode: Optional[int] = None) -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__
        self.statusCode = statusCode or 500

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(message={self.message!r}, statusCode={self.statusCode!r})'

class Requester:

    def __init__(self, headers: Optional[Dict[str, str]] = None):
        self.headers = headers or {}
        self.client = httpx.AsyncClient()

    async def get(self, url: str, dataDict: Optional[JSON] = None, data: Optional[bytes] = None, timeout: Optional[int] = 10, headers: Optional[httpx.Headers] = None, outputFilePath: Optional[str] = None) -> KibaResponse:
        return await self.make_request(method='GET', url=url, dataDict=dataDict, data=data, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def post(self, url: str, dataDict: Optional[JSON] = None, data: Optional[bytes] = None, timeout: Optional[int] = 10, headers: Optional[httpx.Headers] = None, outputFilePath: Optional[str] = None) -> KibaResponse:
        return await self.make_request(method='POST', url=url, dataDict=dataDict, data=data, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def post_json(self, url: str, dataDict: Optional[JSON] = None, timeout: Optional[int] = 10, headers: Optional[httpx.Headers] = None, outputFilePath: Optional[str] = None) -> KibaResponse:
        headers = headers or httpx.Headers()
        headers.update({'Content-Type': 'application/json'})
        return await self.make_request(method='POST', url=url, dataDict=dataDict, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def post_form(self, url: str, formDataDict: Optional[Dict[str, Union[str, FileContent]]] = None, timeout: Optional[int] = 10, headers: Optional[httpx.Headers] = None, outputFilePath: Optional[str] = None) -> KibaResponse:
        headers = headers or httpx.Headers()
        # headers.update({'Content-Type': 'multipart/form-data'})
        return await self.make_request(method='POST', url=url, formDataDict=formDataDict, timeout=timeout, headers=headers, outputFilePath=outputFilePath)

    async def make_request(self, method: str, url: str, dataDict: Optional[JSON] = None, data: Optional[bytes] = None, formDataDict: Optional[Dict[str, Union[str, FileContent]]] = None, timeout: Optional[int] = 10, headers: Optional[Dict[str, str]] = None, outputFilePath: Optional[str] = None) -> KibaResponse:
        files: List[Mapping[str, Union[FileContent, str]]] = None
        if dataDict is not None:
            if data is not None:
                logging.error('Error: dataDict and data should never both be provided to make_request. data will be overwritten by dataDict.')
            if method == 'GET':
                urlParts = urlparse.urlparse(url)
                currentQuery = urlparse.parse_qs(urlParts.query)
                queryString = urlparse.urlencode(dict_util.merge_dicts(currentQuery, dataDict), doseq=True)
                url = urlparse.urlunsplit(components=(urlParts.scheme, urlParts.netloc, urlParts.path, queryString, urlParts.fragment))
            if method == 'POST':
                # TODO(krishan711): this should only happen if json is in the content headers
                data = json.dumps(dataDict).encode()
        if formDataDict:
            if method == 'POST':
                files = {}
                data = {}
                for name, value in formDataDict.items():
                    if isinstance(value, str):
                        data[name] = value
                    elif isinstance(value, IOBase):
                        files[name] = value
            else:
                logging.error('Error: formDataDict should only be passed into POST requests.')
        request = httpx.Request(method=method, url=url, data=data, files=files, headers={**self.headers, **(headers or {})})
        httpxResponse = await self.client.send(request=request, timeout=timeout)
        if 400 <= httpxResponse.status_code < 600:
            raise ResponseException(message=httpxResponse.text, statusCode=httpxResponse.status_code)
        # TODO(krishan711): this would be more efficient if streamed
        if outputFilePath is not None:
            if os.path.dirname(outputFilePath):
                os.makedirs(os.path.dirname(outputFilePath), exist_ok=True)
            await file_util.write_file_bytes(filePath=outputFilePath, content=httpxResponse.content)
        return httpxResponse

    async def close_connections(self) -> None:
        await self.client.aclose()
