from cassian.domain.models import JobView
from cassian.infra.queueing import JobQueue
from cassian.services.job_state import AppState


class JobController:
    def __init__(self, state: AppState, job_queue: JobQueue) -> None:
        self.state = state
        self.job_queue = job_queue

    async def submit_job(self, total_records: int, chunk_size: int) -> JobView:
        job = self.state.create_job(
            total_records=total_records,
            chunk_size=chunk_size,
        )

        try:
            await self.job_queue.enqueue(job.job_id)
        except Exception:
            self.state.mark_submission_failed(job.job_id)
            raise

        return self.state.mark_queued(job.job_id)

    async def restore_jobs(self, *, requeue_submitting_only: bool) -> None:
        job_ids_to_enqueue = self.state.restore_incomplete_jobs(
            requeue_submitting_only=requeue_submitting_only
        )

        for job_id in job_ids_to_enqueue:
            await self.job_queue.enqueue(job_id)

    def get_job(self, job_id: str) -> JobView | None:
        return self.state.get_job(job_id)

    def list_jobs(self) -> list[JobView]:
        return self.state.list_jobs()
