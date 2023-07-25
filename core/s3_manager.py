import dataclasses
import mimetypes
import os
import random
from contextlib import AsyncExitStack
from string import ascii_letters
from typing import TYPE_CHECKING
from typing import Any
from typing import AsyncGenerator
from typing import Dict
from typing import Optional
from typing import Sequence
from typing import Tuple

from aiobotocore.session import get_session as get_botocore_session
from botocore.exceptions import ClientError
from httpx import Headers

from core import logging
from core.exceptions import InternalServerErrorException
from core.exceptions import NotFoundException
from core.util import file_util

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client
else:
    S3Client = Any



@dataclasses.dataclass
class PresignedUploadField:
    name: str
    value: str

@dataclasses.dataclass
class S3PresignedUpload:
    url: str
    fields: Sequence[PresignedUploadField]

@dataclasses.dataclass
class S3File:
    bucket: str
    path: str

class S3Manager:

    def __init__(self, region: str, accessKeyId: str, accessKeySecret: str):
        self.region = region
        self._accessKeyId = accessKeyId
        self._accessKeySecret = accessKeySecret
        self._exitStack = AsyncExitStack()
        self._s3Client: Optional[S3Client] = None

    async def connect(self) -> None:
        session = get_botocore_session()
        self._s3Client = await self._exitStack.enter_async_context(session.create_client('s3', region_name=self.region, aws_access_key_id=self._accessKeyId, aws_secret_access_key=self._accessKeySecret))

    async def disconnect(self) -> None:
        await self._exitStack.aclose()
        self._s3Client = None

    @staticmethod
    def _split_path_to_bucket_key(path: str) -> Tuple[str, str]:
        if path.startswith('s3://'):
            path = path[len('s3://'):]
        paths = path.split('/')
        return paths[0], '/'.join(paths[1:]) if len(paths) > 0 else ''

    @staticmethod
    def _get_extra_args(accessControl: Optional[str] = None, cacheControl: Optional[str] = None, contentType: Optional[str] = None, shouldUseAesEncryption: bool = False) -> Dict[str, str]:
        extraArgs = {}
        if accessControl is not None:
            extraArgs['ACL'] = accessControl
        if contentType:
            extraArgs['ContentType'] = contentType
        if cacheControl:
            extraArgs['CacheControl'] = cacheControl
        if shouldUseAesEncryption:
            extraArgs['ServerSideEncryption'] = 'AES256'
        return extraArgs

    @staticmethod
    def _generate_random_filename() -> str:
        return f'random_file_{"".join(random.choice(ascii_letters) for _ in range(20))}'

    async def write_file(self, content: bytes, targetPath: str, accessControl: Optional[str] = None, cacheControl: Optional[str] = None, contentType: Optional[str] = None) -> None:
        if not self._s3Client:
            raise InternalServerErrorException("You need to call .connect() before trying to write to s3")
        targetBucket, targetKey = self._split_path_to_bucket_key(path=targetPath)
        extraArgs = self._get_extra_args(accessControl=accessControl, cacheControl=cacheControl, contentType=contentType or self._get_file_mimetype(fileName=targetKey))
        await self._s3Client.put_object(Body=content, Bucket=targetBucket, Key=targetKey, **extraArgs)  # type: ignore[arg-type]

    async def upload_file(self, filePath: str, targetPath: str, accessControl: Optional[str] = None, cacheControl: Optional[str] = None, contentType: Optional[str] = None) -> None:
        if not self._s3Client:
            raise InternalServerErrorException("You need to call .connect() before trying to write to s3")
        content = await file_util.read_file_bytes(filePath=filePath)
        await self.write_file(content=content, targetPath=targetPath, accessControl=accessControl, cacheControl=cacheControl, contentType=contentType)

    async def read_file(self, sourcePath: str) -> bytes:
        if not self._s3Client:
            raise InternalServerErrorException("You need to call .connect() before trying to read from s3")
        bucket, key = self._split_path_to_bucket_key(path=sourcePath)
        response = await self._s3Client.get_object(Bucket=bucket, Key=key)
        async with response['Body'] as stream:
            output = await stream.read()
        return output

    async def download_file(self, sourcePath: str, filePath: str) -> None:
        if not self._s3Client:
            raise InternalServerErrorException("You need to call .connect() before trying to read from s3")
        content = await self.read_file(sourcePath=sourcePath)
        await file_util.write_file_bytes(filePath=filePath, content=content)

    async def copy_file(self, source: str, target: str, accessControl: Optional[str] = None, cacheControl: Optional[str] = None, contentType: Optional[str] = None) -> None:
        if not self._s3Client:
            raise InternalServerErrorException("You need to call .connect() before trying to write to s3")
        logging.info(f'Copying file from {source} to {target}')
        sourceBucket, sourceKey = self._split_path_to_bucket_key(path=source)
        targetBucket, targetKey = self._split_path_to_bucket_key(path=target)
        extraArgs = self._get_extra_args(accessControl=accessControl, cacheControl=cacheControl, contentType=contentType or self._get_file_mimetype(fileName=targetKey))
        await self._s3Client.copy_object(CopySource={'Bucket': sourceBucket, 'Key': sourceKey}, Bucket=targetBucket, Key=targetKey, MetadataDirective='REPLACE', **extraArgs)  # type: ignore[arg-type]

    async def delete_file(self, filePath: str) -> None:
        if not self._s3Client:
            raise InternalServerErrorException("You need to call .connect() before trying to write to s3")
        bucket, key = self._split_path_to_bucket_key(path=filePath)
        await self._s3Client.delete_object(Bucket=bucket, Key=key)

    async def head_file(self, filePath: str) -> Headers:
        if not self._s3Client:
            raise InternalServerErrorException("You need to call .connect() before trying to read from s3")
        bucket, key = self._split_path_to_bucket_key(path=filePath)
        try:
            response = await self._s3Client.head_object(Bucket=bucket, Key=key)
        except ClientError:
            raise NotFoundException()
        return Headers(response['ResponseMetadata'].get('HTTPHeaders', {}))

    async def check_file_exists(self, filePath: str) -> bool:
        if not self._s3Client:
            raise InternalServerErrorException("You need to call .connect() before trying to read from s3")
        bucket, key = self._split_path_to_bucket_key(path=filePath)
        try:
            await self._s3Client.head_object(Bucket=bucket, Key=key)
        except ClientError:
            return False
        return True

    async def list_directory_files(self, s3Directory: str) -> Sequence[S3File]:
        if not self._s3Client:
            raise InternalServerErrorException("You need to call .connect() before trying to read from s3")
        return [s3File async for s3File in self.generate_directory_files(s3Directory=s3Directory)]

    async def generate_directory_files(self, s3Directory: str) -> AsyncGenerator[S3File, None]:
        if not self._s3Client:
            raise InternalServerErrorException("You need to call .connect() before trying to read from s3")
        bucket, prefix = self._split_path_to_bucket_key(path=s3Directory)
        prefix = prefix if prefix.endswith('/') else f'{prefix}/'
        continuationToken: Optional[str] = None
        while True:
            if not continuationToken:
                response = await self._s3Client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=100)
            else:
                response = await self._s3Client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=100, ContinuationToken=continuationToken)
            for item in response.get('Contents', []):
                yield S3File(path=item['Key'], bucket=bucket)
            if not response['IsTruncated']:
                return
            continuationToken = response['NextContinuationToken']

    @staticmethod
    def _get_file_mimetype(fileName: str) -> Optional[str]:
        mimetype, _ = mimetypes.guess_type(fileName)
        return mimetype

    async def copy_directory(self, source: str, target: str, accessControl: Optional[str] = None, cacheControl: Optional[str] = None) -> None:
        if not self._s3Client:
            raise InternalServerErrorException("You need to call .connect() before trying to write to s3")
        logging.info(f'Copying directory from {source} to {target}')
        sourceBucket, sourceKey = self._split_path_to_bucket_key(path=source)
        sourceKey = sourceKey if sourceKey.endswith('/') else f'{sourceKey}/'
        target = target.rstrip('/')
        async for s3File in self.generate_directory_files(s3Directory=source):
            filePathPart = s3File.path.replace(sourceKey, '', 1)
            await self.copy_file(source=f's3://{sourceBucket}/{s3File.path}', target=f'{target}/{filePathPart}', accessControl=accessControl, cacheControl=cacheControl)

    async def upload_directory(self, sourceDirectory: str, target: str, accessControl: Optional[str] = None, cacheControl: Optional[str] = None) -> None:
        if not self._s3Client:
            raise InternalServerErrorException("You need to call .connect() before trying to write to s3")
        logging.info(f'Uploading directory from {sourceDirectory} to {target}')
        sourceDirectory = sourceDirectory if sourceDirectory.endswith('/') else f'{sourceDirectory}/'
        targetBucket, targetKey = self._split_path_to_bucket_key(path=target)
        for root, _, files in os.walk(sourceDirectory):
            for filePath in files:
                localFilePath = os.path.join(root, filePath)
                targetKeyPath = f'{targetKey}/{localFilePath.replace(sourceDirectory, "", 1)}'
                await self.upload_file(filePath=localFilePath, targetPath=f's3://{targetBucket}/{targetKeyPath}', accessControl=accessControl, cacheControl=cacheControl)

    async def generate_presigned_upload(self, target: str, accessControl: Optional[str] = None, cacheControl: Optional[str] = None, timeLimit: int = 60, sizeLimit: int = file_util.MEGABYTE) -> S3PresignedUpload:
        if not self._s3Client:
            raise InternalServerErrorException("You need to call .connect() before trying to write to s3")
        targetBucket, targetKey = self._split_path_to_bucket_key(path=target)
        # fields and conditions cannot be merged https://github.com/boto/boto3/issues/1103
        fields = {}
        conditions = [
            ['content-length-range', 1, sizeLimit],
            ['starts-with', '$Content-Type', ''],
        ]
        if accessControl:
            fields.update(self._get_extra_args(accessControl=accessControl))
            conditions.append(self._get_extra_args(accessControl=accessControl))
        if cacheControl:
            fields['Cache-Control'] = cacheControl
            conditions.append({'Cache-Control': cacheControl})
        response = await self._s3Client.generate_presigned_post(Bucket=targetBucket, Key=targetKey, Fields=fields, Conditions=conditions, ExpiresIn=timeLimit)
        return S3PresignedUpload(url=response['url'], fields=[PresignedUploadField(name=name, value=value) for name, value in response['fields'].items()])
