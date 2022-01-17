from __future__ import annotations

import datetime
from typing import Any
from typing import Dict
from typing import Optional

from pydantic import BaseModel

from core.util import date_util


class Message(BaseModel):
    command: str
    content: Dict[str, Any]
    postDate: Optional[datetime.datetime]

    def set_post_date(self):
        self.postDate = date_util.datetime_from_now()

class SqsMessage(Message):
    receiptHandle: str

    @classmethod
    def from_sqs_message(cls, sqsMessage: Dict[str, Any]) -> SqsMessage:
        message = Message.parse_raw(sqsMessage['Body'])
        return cls(
            command=message.command,
            content=message.content,
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
            postDate=None
        )
