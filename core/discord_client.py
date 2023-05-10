from core.requester import KibaResponse
from core.requester import Requester
from core.notification_client import NotificationClient

class DiscordClient(NotificationClient):

    def __init__(self, webhookUrl: str, requester: Requester):
        self.webhookUrl = webhookUrl
        self.requester = requester

    async def post(self, messageText: str) -> KibaResponse:
        dataDict = {"content": messageText}
        response = await self.requester.post(self.webhookUrl, dataDict=dataDict)
        return response
