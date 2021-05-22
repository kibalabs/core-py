from __future__ import annotations
from typing import Dict
from typing import Any

from pydantic import BaseModel

class Message(BaseModel):
    command: str
    content: Dict[str, Any]

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
    _COMMAND = 'UNKOWN_COMMAND'

    def to_message(self) -> Message:
        return Message(
            command=self._COMMAND,
            content=self.dict(),
        )
