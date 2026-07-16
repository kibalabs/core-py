from __future__ import annotations

import datetime
import hashlib
import typing
import uuid

from pydantic import BaseModel
from pydantic.fields import ModelPrivateAttr

from core.util import date_util
from core.util.typing_util import JsonObject


class Message(BaseModel):
    command: str
    content: JsonObject
    requestId: str | None
    postCount: int | None
    postDate: datetime.datetime | None
    deduplicationId: str | None = None

    def prepare_for_send(self) -> None:
        self.requestId = self.requestId or str(uuid.uuid4()).replace('-', '')
        self.postCount = (self.postCount + 1) if self.postCount else 1
        self.postDate = date_util.datetime_from_now()


class MessageContent(BaseModel):
    _COMMAND = 'UNKNOWN_COMMAND'

    @classmethod
    def get_command(cls) -> str:
        return typing.cast(str, typing.cast(ModelPrivateAttr, cls._COMMAND).get_default())

    def get_deduplication_id(self) -> str | None:
        payload = f'{self.get_command()}:{self.model_dump_json()}'
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_message(self) -> Message:
        return Message(
            command=self.get_command(),
            content=self.model_dump(),
            requestId=None,
            postCount=None,
            postDate=None,
            deduplicationId=self.get_deduplication_id(),
        )


class NonDeduplicatedMessageContent(MessageContent):
    def get_deduplication_id(self) -> str | None:
        return None
