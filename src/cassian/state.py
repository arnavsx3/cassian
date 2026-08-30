import asyncio

from cassian.models import JobStatus, JobView


class AppState:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.jobs: dict[str, JobView] = {}

    async def submit_job(self, job: JobView) -> JobView:
        self.jobs[job.job_id] = job
        await self.queue.put(job.job_id)
        return job

    def get_job(self, job_id: str) -> JobView | None:
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[JobView]:
        return list(self.jobs.values())

    def mark_running(self, job_id: str) -> None:
        job = self.jobs[job_id]
        job.status = JobStatus.RUNNING

    def advance_job(self, job_id: str) -> JobView:
        job = self.jobs[job_id]
        next_value = min(job.processed_records + job.chunk_size, job.total_records)
        job.processed_records = next_value
        job.progress_percent = round(
            (job.processed_records / job.total_records) * 100, 2
        )

        if job.processed_records >= job.total_records:
            job.status = JobStatus.COMPLETED

        return job
