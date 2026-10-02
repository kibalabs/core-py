from core.cron.cron_job_processor import CronJobProcessor
from core.cron.model import ApiRequestCronJob
from core.cron.model import CronJob
from core.exceptions import KibaException
from core.requester import Requester


class ApiRequestCronJobProcessor(CronJobProcessor):
    def __init__(self, requester: Requester) -> None:
        self.requester = requester

    async def process_job(self, job: CronJob) -> None:
        if not isinstance(job, ApiRequestCronJob):
            raise KibaException(message=f'Unsupported job type: {type(job).__name__}')
        await self.requester.make_request(method=job.method, url=job.url, dataDict=job.dataDict, headers=job.headers, timeout=job.timeout)
