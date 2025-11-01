from core import logging
from core.notifications.notification_client import NotificationClient
from core.requester import KibaResponse
from core.requester import Requester


class DiscordClient(NotificationClient):
    def __init__(self, webhookUrl: str, requester: Requester) -> None:
        self.webhookUrl = webhookUrl
        self.requester = requester

    async def post(self, messageText: str) -> KibaResponse:
        if len(messageText) > 1000:  # noqa: PLR2004
            logging.info('Truncating Discord message to 1000 characters')
            messageText = messageText[:997] + '...'
        data = {'content': messageText}
        response = await self.requester.post(self.webhookUrl, dataDict=data, headers={'content-type': 'application/json'})
        return response
