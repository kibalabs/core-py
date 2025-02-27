import datetime
import hashlib
import hmac
from collections.abc import Mapping
from collections.abc import MutableMapping
from collections.abc import Sequence
from typing import Union
from urllib import parse as urlparse

from core.exceptions import InternalServerErrorException
from core.requester import FileContent
from core.requester import HttpxFileTypes
from core.requester import KibaResponse
from core.requester import Requester
from core.util import date_util
from core.util import json_util
from core.util.typing_util import Json


# NOTE(krishan711): mostly adapted from https://docs.aws.amazon.com/general/latest/gr/sigv4-signed-request-examples.html
class AwsRequester(Requester):
    _SIGNING_ALGORITHM = 'AWS4-HMAC-SHA256'

    def __init__(self, accessKeyId: str, accessKeySecret: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(headers=headers)
        self.accessKeyId = accessKeyId
        self.accessKeySecret = accessKeySecret

    @staticmethod
    def _sign(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode(), hashlib.sha256).digest()

    @staticmethod
    def _sign_hex(key: bytes, message: str) -> str:
        return hmac.new(key, message.encode(), hashlib.sha256).hexdigest()

    def _sign_string(self, stringToSign: str, requestDate: datetime.datetime, service: str, region: str) -> str:
        key1 = f'AWS4{self.accessKeySecret}'.encode()
        key2 = self._sign(key=key1, message=requestDate.strftime('%Y%m%d'))
        key3 = self._sign(key=key2, message=region)
        key4 = self._sign(key=key3, message=service)
        key5 = self._sign(key=key4, message='aws4_request')
        return self._sign_hex(key=key5, message=stringToSign)

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
        canonicalQueryString = ''
        if data is None and dataDict is not None:
            if method == 'GET':
                raise InternalServerErrorException('GET requests with parameters are not supported on AwsRequester yet.')
            if method == 'POST':
                data = json_util.dumps(dataDict).encode()
        if not data:
            raise InternalServerErrorException('requests without date are not supported on AwsRequester yet.')
        if formDataDict:
            raise InternalServerErrorException('formDataDict is not supported on AwsRequester yet.')
        if formFiles:
            raise InternalServerErrorException('formFiles is not supported on AwsRequester yet.')
        parsedUrl = urlparse.urlparse(url=url)
        host = parsedUrl.netloc
        path = parsedUrl.path or '/'
        hostParts = host.split('.')
        service = hostParts[-4]
        region = hostParts[-3]
        requestDate = date_util.datetime_from_now()
        amazonFormattedDate = requestDate.strftime('%Y%m%dT%H%M%SZ')
        headers = headers or {}
        headers['x-amz-date'] = amazonFormattedDate
        headers['host'] = host
        # NOTE(krishan711): headers always have to be sorted before signing
        headerKeysToSign = sorted(['host', 'x-amz-date'])
        signedHeadersString = ';'.join(headerKeysToSign)
        canonicalHeaders = ''.join(f'{headerKey}:{headers[headerKey]}\n' for headerKey in headerKeysToSign)
        payloadHash = hashlib.sha256(data).hexdigest()
        canonicalRequest = '\n'.join([method, path, canonicalQueryString, canonicalHeaders, signedHeadersString, payloadHash])  # noqa: FLY002
        requestHash = hashlib.sha256(canonicalRequest.encode()).hexdigest()
        credentialScope = '/'.join([requestDate.strftime('%Y%m%d'), region, service, 'aws4_request'])
        stringToSign = '\n'.join([self._SIGNING_ALGORITHM, amazonFormattedDate, credentialScope, requestHash])  # noqa: FLY002
        signature = self._sign_string(stringToSign=stringToSign, requestDate=requestDate, service=service, region=region)
        headers['Authorization'] = f'{self._SIGNING_ALGORITHM} Credential={self.accessKeyId}/{credentialScope}, SignedHeaders={signedHeadersString}, Signature={signature}'
        return await super().make_request(method=method, url=url, dataDict=None, data=data, formDataDict=None, formFiles=None, timeout=timeout, headers=headers, outputFilePath=outputFilePath)
