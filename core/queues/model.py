from __future__ import annotations

import logging
from typing import Any
from typing import Dict

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
    _COMMAND = None
    COMMAND = 'UNKOWN_COMMAND'

    def to_message(self) -> Message:
        if self._COMMAND:
            logging.warning('Please use COMMAND instead of _COMMAND, which will be removed in 0.3.0')
        return Message(
            command=self._COMMAND or self.COMMAND,
            content=self.dict(),
        )
