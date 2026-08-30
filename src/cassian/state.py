import asyncio

from cassian.models import JobStatus, JobView
from cassian.storage import CheckpointStore, FileCheckpointStore


class AppState:
    def __init__(self, checkpoint_store: CheckpointStore | None = None) -> None:
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.jobs: dict[str, JobView] = {}
        self.checkpoint_store = checkpoint_store or FileCheckpointStore()

    async def submit_job(self, job: JobView) -> JobView:
        self.jobs[job.job_id] = job
        self.checkpoint_store.save_job(job)
        await self.queue.put(job.job_id)
        return job

    def restore_incomplete_jobs(self) -> None:
        for job in self.checkpoint_store.load_all_jobs():
            self.jobs[job.job_id] = job
            if job.status == JobStatus.COMPLETED:
                continue

            if job.processed_records > 0:
                job.status = JobStatus.RECOVERING
                job.recovery_count += 1
            else:
                job.status = JobStatus.QUEUED

            self.checkpoint_store.save_job(job)
            self.queue.put_nowait(job.job_id)

    def get_job(self, job_id: str) -> JobView | None:
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[JobView]:
        return list(self.jobs.values())

    def mark_running(self, job_id: str) -> None:
        job = self.jobs[job_id]
        if job.processed_records == 0:
            job.status = JobStatus.RUNNING
        else:
            job.status = JobStatus.RECOVERING
        self.checkpoint_store.save_job(job)

    def advance_job(self, job_id: str) -> JobView:
        job = self.jobs[job_id]
        next_value = min(job.processed_records + job.chunk_size, job.total_records)
        job.processed_records = next_value
        job.last_checkpoint_records = next_value
        job.progress_percent = round(
            (job.processed_records / job.total_records) * 100,
            2,
        )

        if job.processed_records >= job.total_records:
            job.status = JobStatus.COMPLETED

        self.checkpoint_store.save_job(job)
        return job
