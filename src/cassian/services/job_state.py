from cassian.domain.models import JobStatus, JobView
from cassian.infra.checkpoints import CheckpointStore, FileCheckpointStore
from cassian.services.job_repository import JobRepository
from cassian.workloads.processor import WorkloadProcessor
from datetime import UTC, datetime, timedelta


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

    def attach_worker_launch(
        self,
        job_id: str,
        *,
        instance_id: str,
        instance_type: str,
        market_type: str,
    ) -> JobView:
        job = self._require_job(job_id)
        job.worker_instance_id = instance_id
        job.worker_instance_type = instance_type
        job.worker_market_type = market_type
        return self.job_repository.save(job)

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
        now = datetime.now(UTC)

        job.status = (
            JobStatus.RUNNING if job.processed_records == 0 else JobStatus.RECOVERING
        )
        job.worker_started_at = now
        job.worker_heartbeat_at = now
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

    def request_worker_launch(
        self,
        job_id: str,
        *,
        now: datetime | None = None,
    ) -> JobView:
        job = self._require_job(job_id)
        job.worker_launch_requested_at = now or datetime.now(UTC)
        return self.job_repository.save(job)

    def begin_recovery(
        self,
        job_id: str,
        *,
        now: datetime | None = None,
    ) -> JobView:
        job = self._require_job(job_id)
        job.status = JobStatus.RECOVERING
        job.recovery_count += 1
        job.worker_instance_id = None
        job.worker_instance_type = None
        job.worker_market_type = None
        job.worker_started_at = None
        job.worker_heartbeat_at = None
        job.worker_launch_requested_at = now or datetime.now(UTC)
        return self.job_repository.save(job)

    def record_worker_heartbeat(
        self,
        job_id: str,
        *,
        now: datetime | None = None,
    ) -> JobView:
        job = self._require_job(job_id)
        job.worker_heartbeat_at = now or datetime.now(UTC)
        return self.job_repository.save(job)

    def find_stale_worker_jobs(
        self,
        *,
        stale_after: timedelta,
        now: datetime | None = None,
    ) -> list[JobView]:
        current_time = now or datetime.now(UTC)
        cutoff = current_time - stale_after
        stale_jobs: list[JobView] = []

        for job in self.job_repository.list():
            if job.status not in {
                JobStatus.QUEUED,
                JobStatus.RUNNING,
                JobStatus.RECOVERING,
            }:
                continue

            last_signal = job.worker_heartbeat_at or job.worker_launch_requested_at

            if last_signal is not None and last_signal <= cutoff:
                stale_jobs.append(job)

        return stale_jobs
