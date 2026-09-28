import datetime

from pydantic import BaseModel

from core.util import date_util


class Lease(BaseModel):
    name: str
    token: str
    expiryDate: datetime.datetime
    isLost: bool = False

    def is_valid(self) -> bool:
        return not self.isLost and date_util.datetime_from_now() < self.expiryDate
