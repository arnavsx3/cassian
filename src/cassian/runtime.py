from dataclasses import dataclass

from cassian.controller.job_controller import JobController
from cassian.core.config import Settings, get_settings
from cassian.infra.checkpoints import CheckpointStore, build_checkpoint_store
from cassian.infra.queueing import InMemoryJobQueue, JobQueue, SqsJobQueue
from cassian.services.job_state import AppState
from cassian.workers.local_worker import LocalWorker


@dataclass(slots=True)
class AppRuntime:
    settings: Settings
    checkpoint_store: CheckpointStore
    job_queue: JobQueue
    job_state: AppState
    job_controller: JobController
    worker: LocalWorker


def build_job_queue(settings: Settings) -> JobQueue:
    if settings.queue_backend == "memory":
        return InMemoryJobQueue()

    if not settings.aws_region:
        raise ValueError("AWS_REGION is required when QUEUE_BACKEND=sqs")
    if not settings.sqs_queue_url:
        raise ValueError("SQS_QUEUE_URL is required when QUEUE_BACKEND=sqs")

    return SqsJobQueue(
        queue_url=settings.sqs_queue_url,
        region_name=settings.aws_region,
        wait_time_seconds=settings.sqs_wait_time_seconds,
        visibility_timeout=settings.sqs_visibility_timeout,
    )


def build_runtime(
    settings: Settings | None = None,
    checkpoint_store: CheckpointStore | None = None,
    job_queue: JobQueue | None = None,
) -> AppRuntime:
    settings = settings or get_settings()
    checkpoint_store = checkpoint_store or build_checkpoint_store(settings)
    job_queue = job_queue or build_job_queue(settings)

    job_state = AppState(checkpoint_store=checkpoint_store)
    job_controller = JobController(state=job_state, job_queue=job_queue)
    worker = LocalWorker(
        state=job_state,
        job_queue=job_queue,
        chunk_delay_seconds=settings.worker_chunk_delay_seconds,
    )

    return AppRuntime(
        settings=settings,
        checkpoint_store=checkpoint_store,
        job_queue=job_queue,
        job_state=job_state,
        job_controller=job_controller,
        worker=worker,
    )
