from __future__ import annotations

import datetime
import uuid
from typing import Any
from typing import Dict
from typing import Optional

from pydantic import BaseModel

from core.util import date_util


class Message(BaseModel):
    command: str
    content: Dict[str, Any]  # type: ignore[misc]
    requestId: Optional[str]
    postCount: Optional[int]
    postDate: Optional[datetime.datetime]

    def prepare_for_send(self) -> None:
        self.requestId = self.requestId or str(uuid.uuid4()).replace('-', '')
        self.postCount = (self.postCount + 1) if self.postCount else 1
        self.postDate = date_util.datetime_from_now()


class MessageContent(BaseModel):
    _COMMAND = 'UNKNOWN_COMMAND'

    @classmethod
    def get_command(cls) -> str:
        return str(cls._COMMAND)

    def to_message(self) -> Message:
        return Message(
            command=self.get_command(),
            content=self.model_dump(),
            requestId=None,
            postCount=None,
            postDate=None,
        )
