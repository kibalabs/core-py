from core.requester import KibaResponse
from core.requester import Requester
from core.notification_client import NotificationsClient

class DiscordClient(NotificationsClient):

    def __init__(self, webhookUrl: str, requester: Requester) -> KibaResponse:
        self.webhookUrl = webhookUrl
        self.requester = requester

    async def post(self, messageText: str):
        dataDict = {"content": messageText}
        response = await self.requester.post(self.webhookUrl, dataDict=dataDict)
        return response
