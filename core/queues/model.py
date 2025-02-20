from __future__ import annotations

import datetime
import typing
import uuid
from typing import Any

from pydantic import BaseModel
from pydantic.fields import ModelPrivateAttr

from core.util import date_util


class Message(BaseModel):  # type: ignore[explicit-any]
    command: str
    content: dict[str, Any]  # type: ignore[explicit-any]
    requestId: str | None
    postCount: int | None
    postDate: datetime.datetime | None

    def prepare_for_send(self) -> None:
        self.requestId = self.requestId or str(uuid.uuid4()).replace('-', '')
        self.postCount = (self.postCount + 1) if self.postCount else 1
        self.postDate = date_util.datetime_from_now()


class MessageContent(BaseModel):
    _COMMAND = 'UNKNOWN_COMMAND'

    @classmethod
    def get_command(cls) -> str:
        return typing.cast(str, typing.cast(ModelPrivateAttr, cls._COMMAND).get_default())

    def to_message(self) -> Message:
        return Message(
            command=self.get_command(),
            content=self.model_dump(),
            requestId=None,
            postCount=None,
            postDate=None,
        )
