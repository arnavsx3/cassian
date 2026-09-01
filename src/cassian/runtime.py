from dataclasses import dataclass

from cassian.controller.ec2_launcher import Ec2WorkerLauncher
from cassian.controller.job_controller import JobController
from cassian.controller.worker_dispatcher import WorkerDispatcher
from cassian.core.aws import build_sqs_client
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

    if not settings.sqs_queue_url:
        raise ValueError("SQS_QUEUE_URL is required when QUEUE_BACKEND=sqs")

    sqs_client = build_sqs_client(settings)
    return SqsJobQueue(
        queue_url=settings.sqs_queue_url,
        client=sqs_client,
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

    worker_dispatcher = WorkerDispatcher(
        settings=settings,
        ec2_launcher=Ec2WorkerLauncher(settings)
        if settings.worker_execution_mode == "ec2"
        else None,
    )

    job_controller = JobController(
        state=job_state,
        job_queue=job_queue,
        worker_dispatcher=worker_dispatcher,
        enqueue_jobs=settings.worker_execution_mode == "local",
        max_worker_launch_attempts=settings.max_worker_launch_attempts,
    )

    worker = LocalWorker(
        state=job_state,
        job_queue=job_queue,
        chunk_delay_seconds=settings.worker_chunk_delay_seconds,
        poll_interval_seconds=settings.worker_poll_interval_seconds,
    )

    return AppRuntime(
        settings=settings,
        checkpoint_store=checkpoint_store,
        job_queue=job_queue,
        job_state=job_state,
        job_controller=job_controller,
        worker=worker,
    )
