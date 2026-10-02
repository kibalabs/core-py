from typing import ClassVar

from core.cron.cron_job_processor import CronJobProcessor
from core.cron.model import CronJob
from core.exceptions import KibaException
from core.requester import Requester
from core.util.typing_util import Json


class ApiRequestCronJob(CronJob):
    jobType: ClassVar[str] = 'api_request'
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


class ApiRequestCronJobProcessor(CronJobProcessor):
    jobTypes: ClassVar[frozenset[str]] = frozenset({ApiRequestCronJob.jobType})

    def __init__(self, requester: Requester) -> None:
        self.requester = requester

    async def process_job(self, job: CronJob) -> None:
        if not isinstance(job, ApiRequestCronJob):
            raise KibaException(message=f'{type(self).__name__} cannot process {type(job).__name__}')
        await self.requester.make_request(method=job.method, url=job.url, dataDict=job.dataDict, headers=job.headers, timeout=job.timeout)
