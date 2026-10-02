from pydantic import BaseModel

from core.util.typing_util import Json


class CronJob(BaseModel):
    name: str
    weeks: int = 0
    days: int = 0
    hours: int = 0
    minutes: int = 0
    seconds: int = 0
    jitter: int = 0
    crontab: str | None = None

    @property
    def query(self) -> dict[str, str]:
        return {}


class ApiRequestCronJob(CronJob):
    method: str
    url: str
    dataDict: Json | None = None
    headers: dict[str, str] | None = None
    timeout: int | None = None

    @property
    def query(self) -> dict[str, str]:
        if not isinstance(self.dataDict, dict):
            return {}
        return {key: str(value) for key, value in self.dataDict.items() if isinstance(value, str | int | float | bool)}
