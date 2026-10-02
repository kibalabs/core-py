from typing import ClassVar

from pydantic import BaseModel


class CronJob(BaseModel):
    jobType: ClassVar[str]
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
