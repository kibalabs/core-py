from typing import Optional

from core.requester import KibaResponse
from core.requester import Requester
from core.notification_client import NotificationsClient

class SlackClient(NotificationsClient):

    def __init__(self, webhookUrl: str, requester: Requester, defaultChannel: str, defaultSender: Optional[str] = 'kiba-server', defaultIconEmoji: Optional[str] = ':robot_face:') -> None:
        self.webhookUrl = webhookUrl
        self.requester = requester
        self.defaultChannel = defaultChannel
        self.defaultSender = defaultSender
        self.defaultIconEmoji = defaultIconEmoji

    async def post(self, messageText: str) -> KibaResponse:
        response = await self.requester.post_json(url=self.webhookUrl, dataDict={
            'text': messageText,
            'username': self.defaultSender,
            'channel': self.defaultChannel,
            'icon_emoji': self.defaultIconEmoji,
        })
        return response
