import pytest

from core.cron.cron_executor import CronExecutor
from core.cron.cron_job_processor import CronJobProcessor
from core.cron.model import CronJob


class RecordingProcessor(CronJobProcessor):
    def __init__(self, failingJobNames: set[str]) -> None:
        self.failingJobNames = failingJobNames
        self.processedJobNames: list[str] = []

    async def process_job(self, job: CronJob) -> None:
        self.processedJobNames.append(job.name)
        if job.name in self.failingJobNames:
            raise ValueError(f'{job.name} failed')


@pytest.mark.asyncio
async def test_failing_job_does_not_stop_later_jobs() -> None:
    processor = RecordingProcessor(failingJobNames={'first'})
    executor = CronExecutor(jobs=[], jobProcessor=processor)

    await executor.execute_job(job=CronJob(name='first', minutes=1))
    await executor.execute_job(job=CronJob(name='second', minutes=1))

    assert processor.processedJobNames == ['first', 'second']
