from __future__ import annotations
import datetime

from typing import Any, Optional
from typing import Dict

from pydantic import BaseModel
from util import date_util


class Message(BaseModel):
    command: str
    content: Dict[str, Any]
    postDate: Optional[datetime.datetime]

class SqsMessage(Message):
    receiptHandle: str

    @classmethod
    def from_sqs_message(cls, sqsMessage: Dict[str, Any]) -> SqsMessage:
        message = Message.parse_raw(sqsMessage['Body'])
        return cls(
            command=message.command,
            content=message.content,
            receiptHandle=sqsMessage['ReceiptHandle'],
        )

class MessageContent(BaseModel):
    _COMMAND = 'UNKNOWN_COMMAND'

    @classmethod
    def get_command(cls) -> str:
        return cls._COMMAND

    def to_message(self) -> Message:
        postDate =date_util.datetime_from_now()
        return Message(
            command=self.get_command(),
            content=self.dict(),
            postDate=postDate,
        )
