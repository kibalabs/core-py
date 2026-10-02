import abc
from abc import ABC
from typing import ClassVar

from core.cron.model import CronJob


class CronJobProcessor(ABC):
    jobTypes: ClassVar[frozenset[str]]

    @abc.abstractmethod
    async def process_job(self, job: CronJob) -> None:
        raise NotImplementedError
