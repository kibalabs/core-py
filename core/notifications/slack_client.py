from core.notifications.notification_client import NotificationClient
from core.requester import KibaResponse
from core.requester import Requester


class SlackClient(NotificationClient):
    def __init__(self, webhookUrl: str, requester: Requester, defaultChannel: str, defaultSender: str | None = 'kiba-server', defaultIconEmoji: str | None = ':robot_face:') -> None:
        self.webhookUrl = webhookUrl
        self.requester = requester
        self.defaultChannel = defaultChannel
        self.defaultSender = defaultSender
        self.defaultIconEmoji = defaultIconEmoji

    async def post(self, messageText: str) -> KibaResponse:
        response = await self.requester.post_json(
            url=self.webhookUrl,
            dataDict={
                'text': messageText,
                'username': self.defaultSender,
                'channel': self.defaultChannel,
                'icon_emoji': self.defaultIconEmoji,
            },
        )
        return response
