from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import Optional

from pydantic import BaseModel

from core.util import date_util

if TYPE_CHECKING:
    from types_aiobotocore_sqs.type_defs import MessageTypeDef as RawSqsMessage


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


class SqsMessage(Message):
    receiptHandle: str

    @classmethod
    def from_sqs_message(cls, sqsMessage: RawSqsMessage) -> SqsMessage:
        message = Message.parse_raw(sqsMessage['Body'])
        return cls(
            command=message.command,
            content=message.content,
            requestId=message.requestId,
            postCount=message.postCount,
            postDate=message.postDate,
            receiptHandle=sqsMessage['ReceiptHandle'],
        )


class MessageContent(BaseModel):
    _COMMAND = 'UNKNOWN_COMMAND'

    @classmethod
    def get_command(cls) -> str:
        return cls._COMMAND

    def to_message(self) -> Message:
        return Message(
            command=self.get_command(),
            content=self.dict(),
            requestId=None,
            postCount=None,
            postDate=None,
        )
