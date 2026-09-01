import logging
from datetime import UTC, datetime, timedelta

from cassian.controller.worker_dispatcher import WorkerDispatchPort
from cassian.domain.models import JobView
from cassian.infra.queueing import JobQueue
from cassian.services.job_state import AppState

logger = logging.getLogger(__name__)
class JobController:
    def __init__(
        self,
        state: AppState,
        job_queue: JobQueue,
        worker_dispatcher: WorkerDispatchPort | None = None,
        enqueue_jobs: bool = True,
    ) -> None:
        self.state = state
        self.job_queue = job_queue
        self.worker_dispatcher = worker_dispatcher
        self.enqueue_jobs = enqueue_jobs

    async def submit_job(self, total_records: int, chunk_size: int) -> JobView:
        job = self.state.create_job(
            total_records=total_records,
            chunk_size=chunk_size,
        )

        try:
            job = self.state.mark_queued(job.job_id)

            if self.enqueue_jobs:
                await self.job_queue.enqueue(job.job_id)

            if self.worker_dispatcher is not None:
                self.state.request_worker_launch(job.job_id)
                launch = self.worker_dispatcher.dispatch(job_id=job.job_id)
                if launch is not None:
                    job = self.state.attach_worker_launch(
                        job.job_id,
                        instance_id=launch.instance_id,
                        instance_type=launch.instance_type,
                        market_type=launch.market_type,
                    )
        except Exception:
            self.state.mark_submission_failed(job.job_id)
            raise

        return job

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
            recovering_job = self.state.begin_recovery(
                stale_job.job_id,
                now=current_time,
            )

            try:
                launch = self.worker_dispatcher.dispatch(
                    job_id=recovering_job.job_id
                )
                if launch is None:
                    raise RuntimeError("EC2 worker dispatch returned no launch result")

                relaunched_jobs.append(
                    self.state.attach_worker_launch(
                        recovering_job.job_id,
                        instance_id=launch.instance_id,
                        instance_type=launch.instance_type,
                        market_type=launch.market_type,
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to relaunch stale worker for job %s",
                    recovering_job.job_id,
                )

        return relaunched_jobs
