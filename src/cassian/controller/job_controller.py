import logging
from datetime import UTC, datetime, timedelta

from cassian.controller.worker_dispatcher import WorkerDispatchPort
from cassian.domain.models import JobView
from cassian.infra.queueing import JobQueue
from cassian.services.job_state import AppState, WorkerFencedError

logger = logging.getLogger(__name__)


class JobController:
    def __init__(
        self,
        state: AppState,
        job_queue: JobQueue,
        worker_dispatcher: WorkerDispatchPort | None = None,
        enqueue_jobs: bool = True,
        max_worker_launch_attempts: int = 3,
    ) -> None:
        self.state = state
        self.job_queue = job_queue
        self.worker_dispatcher = worker_dispatcher
        self.enqueue_jobs = enqueue_jobs
        self.max_worker_launch_attempts = max_worker_launch_attempts

    async def submit_job(self, total_records: int, chunk_size: int) -> JobView:
        job = self.state.create_job(
            total_records=total_records,
            chunk_size=chunk_size,
        )

        try:
            job = self.state.mark_queued(job.job_id)

            if self.enqueue_jobs:
                await self.job_queue.enqueue(job.job_id)
                return job

            return self._launch_worker(job.job_id)
        except Exception:
            self.state.mark_submission_failed(job.job_id)
            raise

    async def restore_jobs(self, *, requeue_submitting_only: bool) -> None:
        job_ids_to_enqueue = self.state.restore_incomplete_jobs(
            requeue_submitting_only=requeue_submitting_only
        )

        if not self.enqueue_jobs:
            return

        for job_id in job_ids_to_enqueue:
            await self.job_queue.enqueue(job_id)

    def get_job(self, job_id: str) -> JobView | None:
        return self.state.get_job(job_id)

    def list_jobs(self) -> list[JobView]:
        return self.state.list_jobs()

    async def reconcile_stale_workers(
        self,
        *,
        stale_after: timedelta,
        now: datetime | None = None,
    ) -> list[JobView]:
        if self.enqueue_jobs or self.worker_dispatcher is None:
            return []

        current_time = now or datetime.now(UTC)
        relaunched_jobs: list[JobView] = []

        for stale_job in self.state.find_stale_worker_jobs(
            stale_after=stale_after,
            now=current_time,
        ):
            try:
                if stale_job.worker_instance_id is not None:
                    self.worker_dispatcher.terminate(
                        instance_id=stale_job.worker_instance_id
                    )

                self.state.begin_recovery(
                    stale_job.job_id,
                    expected_generation=stale_job.worker_generation,
                    now=current_time,
                )
                relaunched_jobs.append(self._launch_worker(stale_job.job_id))
            except WorkerFencedError:
                logger.info(
                    "Skipping stale recovery for job %s because it changed",
                    stale_job.job_id,
                )
            except Exception:
                logger.exception(
                    "Failed to recover stale worker for job %s",
                    stale_job.job_id,
                )

        return relaunched_jobs

    def _launch_worker(self, job_id: str) -> JobView:
        if self.worker_dispatcher is None:
            raise RuntimeError("Worker dispatcher is not configured")

        launch_request = self.state.request_worker_launch(
            job_id,
            max_attempts=self.max_worker_launch_attempts,
        )
        launch = self.worker_dispatcher.dispatch(
            job_id=job_id,
            worker_generation=launch_request.worker_generation,
        )

        if launch is None:
            raise RuntimeError("EC2 worker dispatch returned no launch result")

        return self.state.attach_worker_launch(
            job_id,
            worker_generation=launch_request.worker_generation,
            instance_id=launch.instance_id,
            instance_type=launch.instance_type,
            market_type=launch.market_type,
        )
