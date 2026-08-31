from cassian.domain.models import JobStatus, JobView
from cassian.infra.checkpoints import CheckpointStore, FileCheckpointStore
from cassian.services.job_repository import JobRepository
from cassian.workloads.processor import WorkloadProcessor


class AppState:
    def __init__(
        self,
        checkpoint_store: CheckpointStore | None = None,
        workload_processor: WorkloadProcessor | None = None,
    ) -> None:
        checkpoint_store = checkpoint_store or FileCheckpointStore()
        self.job_repository = JobRepository(checkpoint_store=checkpoint_store)
        self.workload_processor = workload_processor or WorkloadProcessor()

    def create_job(self, total_records: int, chunk_size: int) -> JobView:
        job = JobView.new(total_records=total_records, chunk_size=chunk_size)
        return self.job_repository.create(job)

    def mark_submission_failed(self, job_id: str) -> JobView:
        job = self._require_job(job_id)
        job.status = JobStatus.SUBMISSION_FAILED
        return self.job_repository.save(job)

    def mark_queued(self, job_id: str) -> JobView:
        job = self._require_job(job_id)
        job.status = JobStatus.QUEUED
        return self.job_repository.save(job)

    def restore_incomplete_jobs(
        self,
        *,
        requeue_submitting_only: bool,
    ) -> list[str]:
        job_ids_to_enqueue: list[str] = []

        for job in self.job_repository.list():
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

            self.job_repository.save(job)

            if should_enqueue:
                job_ids_to_enqueue.append(job.job_id)

        return job_ids_to_enqueue

    def get_job(self, job_id: str) -> JobView | None:
        return self.job_repository.get(job_id)

    def list_jobs(self) -> list[JobView]:
        return self.job_repository.list()

    def mark_running(self, job_id: str) -> JobView:
        job = self._require_job(job_id)
        job.status = (
            JobStatus.RUNNING if job.processed_records == 0 else JobStatus.RECOVERING
        )
        return self.job_repository.save(job)

    def advance_job(self, job_id: str) -> JobView:
        job = self._require_job(job_id)
        job = self.workload_processor.process_chunk(job)

        if job.processed_records >= job.total_records:
            job.status = JobStatus.COMPLETED

        return self.job_repository.save(job)

    def _require_job(self, job_id: str) -> JobView:
        job = self.job_repository.get(job_id)
        if job is None:
            raise KeyError(f"Unknown job_id: {job_id}")
        return job
