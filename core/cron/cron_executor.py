import asyncio
import datetime
import time
import urllib.parse as urlparse
from collections.abc import Sequence

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

from core import logging
from core.cron.cron_job_processor import CronJobProcessor
from core.cron.model import CronJob
from core.exceptions import KibaException

# NOTE(krishan711): interval jobs are anchored to a fixed date so a restart keeps the same schedule instead of restarting every interval from boot
INTERVAL_START_DATE = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)


class CronExecutor:
    def __init__(self, jobs: Sequence[CronJob], jobProcessors: Sequence[CronJobProcessor]) -> None:
        self.jobs = jobs
        self.processorByJobType: dict[str, CronJobProcessor] = {}
        for jobProcessor in jobProcessors:
            for jobType in jobProcessor.jobTypes:
                existingProcessor = self.processorByJobType.get(jobType)
                if existingProcessor is not None:
                    raise KibaException(message=f'Cron job type {jobType} is handled by both {type(existingProcessor).__name__} and {type(jobProcessor).__name__}')
                self.processorByJobType[jobType] = jobProcessor
        unprocessableJobNames = [job.name for job in jobs if job.jobType not in self.processorByJobType]
        if unprocessableJobNames:
            raise KibaException(message=f'No cron job processor for jobs: {", ".join(unprocessableJobNames)}')
        self.scheduler = AsyncIOScheduler()

    async def execute_job(self, job: CronJob) -> None:
        path = job.name.replace(' ', '_').replace(':', '_').lower()
        query = urlparse.urlencode(job.query, doseq=True)
        logging.api(action='CRON', path=path, pathPattern=path, query=query)
        startTime = time.time()
        statusCode = 200
        try:
            await self.processorByJobType[job.jobType].process_job(job=job)
        except Exception as exception:  # noqa: BLE001
            statusCode = exception.statusCode if isinstance(exception, KibaException) else 500
            logging.error('Caught exception whilst processing cron job:')
            logging.exception(exception)
        duration = time.time() - startTime
        logging.api(action='CRON', path=path, pathPattern=path, query=query, response=statusCode, duration=duration)

    def _build_trigger(self, job: CronJob) -> CronTrigger | IntervalTrigger:
        if job.crontab:
            return CronTrigger.from_crontab(expr=job.crontab)
        return IntervalTrigger(weeks=job.weeks, days=job.days, hours=job.hours, minutes=job.minutes, seconds=job.seconds, jitter=job.jitter, start_date=INTERVAL_START_DATE)

    async def start(self) -> None:
        logging.info(f'Initializing CronExecutor with {len(self.jobs)} jobs')
        for job in self.jobs:
            self.scheduler.add_job(func=self.execute_job, kwargs={'job': job}, trigger=self._build_trigger(job=job), id=job.name, name=job.name, replace_existing=True)
        self.scheduler.start()
        logging.info('CronExecutor started successfully')

    async def run(self) -> None:
        await self.start()
        try:
            await asyncio.Event().wait()
        finally:
            logging.info('Shutting down scheduler...')
            self.scheduler.shutdown()
