from core.notifications.notification_client import NotificationClient
from core.requester import KibaResponse
from core.requester import Requester


class DiscordClient(NotificationClient):
    def __init__(self, webhookUrl: str, requester: Requester) -> None:
        self.webhookUrl = webhookUrl
        self.requester = requester

    async def post(self, messageText: str) -> KibaResponse:
        data = {'content': messageText}
        response = await self.requester.post(self.webhookUrl, dataDict=data, headers={'content-type': 'application/json'})
        return response
