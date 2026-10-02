from typing import ClassVar

import pytest

from core.cron.cron_executor import CronExecutor
from core.cron.cron_job_processor import CronJobProcessor
from core.cron.model import CronJob
from core.exceptions import KibaException


class EmailCronJob(CronJob):
    jobType: ClassVar[str] = 'email'


class ReportCronJob(CronJob):
    jobType: ClassVar[str] = 'report'


class RecordingProcessor(CronJobProcessor):
    def __init__(self, failingJobNames: frozenset[str] = frozenset()) -> None:
        self.failingJobNames = failingJobNames
        self.processedJobNames: list[str] = []

    async def process_job(self, job: CronJob) -> None:
        self.processedJobNames.append(job.name)
        if job.name in self.failingJobNames:
            raise ValueError(f'{job.name} failed')


class EmailProcessor(RecordingProcessor):
    jobTypes: ClassVar[frozenset[str]] = frozenset({EmailCronJob.jobType})


class ReportProcessor(RecordingProcessor):
    jobTypes: ClassVar[frozenset[str]] = frozenset({ReportCronJob.jobType})


class EmailAndReportProcessor(RecordingProcessor):
    jobTypes: ClassVar[frozenset[str]] = frozenset({EmailCronJob.jobType, ReportCronJob.jobType})


@pytest.mark.asyncio
async def test_jobs_are_routed_to_the_processor_for_their_type() -> None:
    emailProcessor = EmailProcessor()
    reportProcessor = ReportProcessor()
    emailJob = EmailCronJob(name='send-emails', minutes=1)
    reportJob = ReportCronJob(name='build-report', minutes=1)
    executor = CronExecutor(jobs=[emailJob, reportJob], jobProcessors=[emailProcessor, reportProcessor])

    await executor.execute_job(job=reportJob)
    await executor.execute_job(job=emailJob)

    assert (emailProcessor.processedJobNames, reportProcessor.processedJobNames) == (['send-emails'], ['build-report'])


@pytest.mark.asyncio
async def test_failing_job_does_not_stop_later_jobs() -> None:
    processor = EmailProcessor(failingJobNames=frozenset({'first'}))
    first, second = EmailCronJob(name='first', minutes=1), EmailCronJob(name='second', minutes=1)
    executor = CronExecutor(jobs=[first, second], jobProcessors=[processor])

    await executor.execute_job(job=first)
    await executor.execute_job(job=second)

    assert processor.processedJobNames == ['first', 'second']


def test_job_without_a_processor_fails_at_startup() -> None:
    with pytest.raises(KibaException, match='No cron job processor for jobs: build-report'):
        CronExecutor(jobs=[ReportCronJob(name='build-report', minutes=1)], jobProcessors=[EmailProcessor()])


def test_job_type_claimed_by_two_processors_fails_at_startup() -> None:
    with pytest.raises(KibaException, match='Cron job type email is handled by both'):
        CronExecutor(jobs=[], jobProcessors=[EmailProcessor(), EmailAndReportProcessor()])
