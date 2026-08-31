from cassian.domain.models import JobStatus, JobView
from cassian.infra.checkpoints import CheckpointStore, FileCheckpointStore


class AppState:
    def __init__(self, checkpoint_store: CheckpointStore | None = None) -> None:
        self.jobs: dict[str, JobView] = {}
        self.checkpoint_store = checkpoint_store or FileCheckpointStore()

    def create_job(self, total_records: int, chunk_size: int) -> JobView:
        job = JobView.new(total_records=total_records, chunk_size=chunk_size)
        self.jobs[job.job_id] = job
        self.checkpoint_store.save_job(job)
        return job

    def mark_submission_failed(self, job_id: str) -> JobView:
        job = self.jobs[job_id]
        job.status = JobStatus.SUBMISSION_FAILED
        self.checkpoint_store.save_job(job)
        return job

    def mark_queued(self, job_id: str) -> JobView:
        job = self.jobs[job_id]
        job.status = JobStatus.QUEUED
        self.checkpoint_store.save_job(job)
        return job

    def restore_incomplete_jobs(
        self,
        *,
        requeue_submitting_only: bool,
    ) -> list[str]:
        job_ids_to_enqueue: list[str] = []

        for job in self.checkpoint_store.load_all_jobs():
            self.jobs[job.job_id] = job

            if job.status == JobStatus.COMPLETED:
                continue

            should_enqueue = False

            if job.status in {JobStatus.SUBMITTING, JobStatus.SUBMISSION_FAILED}:
                job.status = JobStatus.QUEUED
                should_enqueue = True
            elif job.processed_records > 0:
                job.status = JobStatus.RECOVERING
                job.recovery_count += 1
                should_enqueue = not requeue_submitting_only
            else:
                job.status = JobStatus.QUEUED
                should_enqueue = not requeue_submitting_only

            self.checkpoint_store.save_job(job)

            if should_enqueue:
                job_ids_to_enqueue.append(job.job_id)

        return job_ids_to_enqueue

    def get_job(self, job_id: str) -> JobView | None:
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[JobView]:
        return list(self.jobs.values())

    def mark_running(self, job_id: str) -> None:
        job = self.jobs[job_id]
        job.status = (
            JobStatus.RUNNING if job.processed_records == 0 else JobStatus.RECOVERING
        )
        self.checkpoint_store.save_job(job)

    def advance_job(self, job_id: str) -> JobView:
        job = self.jobs[job_id]
        job.processed_records = min(
            job.processed_records + job.chunk_size,
            job.total_records,
        )
        job.last_checkpoint_records = job.processed_records
        job.progress_percent = round(
            (job.processed_records / job.total_records) * 100,
            2,
        )

        if job.processed_records >= job.total_records:
            job.status = JobStatus.COMPLETED

        self.checkpoint_store.save_job(job)
        return job
