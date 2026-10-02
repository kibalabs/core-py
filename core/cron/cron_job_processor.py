import abc
from abc import ABC

from core.cron.model import CronJob


class CronJobProcessor(ABC):
    @abc.abstractmethod
    async def process_job(self, job: CronJob) -> None:
        raise NotImplementedError
