from __future__ import annotations

from pydantic import BaseModel
from pydantic import Json

class Message(BaseModel):
    command: str
    content: Json

class SqsMessage(Message):
    receiptHandle: str

    @classmethod
    def from_sqs_message(cls, sqsMessage: Json) -> SqsMessage:
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
