from typing import Optional

from core.requester import Requester
from core.requester import KibaResponse

class SlackClient:

    def __init__(self, webhookUrl: str, requester: Requester, defaultChannel: str, defaultSender: Optional[str] = 'kiba-server', defaultIconEmoji: Optional[str] = ':robot_face:') -> None:
        self.webhookUrl = webhookUrl
        self.requester = requester
        self.defaultChannel = defaultChannel
        self.defaultSender = defaultSender
        self.defaultIconEmoji = defaultIconEmoji

    async def post(self, text: str) -> KibaResponse:
        response = await self.requester.post_json(url=self.webhookUrl, dataDict={
            'text': text,
            'username': self.defaultSender,
            'channel': self.defaultChannel,
            'icon_emoji': self.defaultIconEmoji,
        })
        return response
