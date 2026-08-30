from contextlib import asynccontextmanager

from fastapi import FastAPI

from cassian.api.routes.health import router as health_router
from cassian.api.routes.jobs import router as jobs_router
from cassian.api.routes.system import router as system_router
from cassian.core.config import Settings, get_settings
from cassian.infra.checkpoints import CheckpointStore, build_checkpoint_store
from cassian.infra.queueing import InMemoryJobQueue, JobQueue, SqsJobQueue
from cassian.services.job_state import AppState
from cassian.workers.local_worker import LocalWorker


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


def create_app(
    settings: Settings | None = None,
    checkpoint_store: CheckpointStore | None = None,
    job_queue: JobQueue | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    checkpoint_store = checkpoint_store or build_checkpoint_store(settings)
    job_queue = job_queue or build_job_queue(settings)
    job_state = AppState(checkpoint_store=checkpoint_store)
    worker = LocalWorker(
        state=job_state,
        job_queue=job_queue,
        chunk_delay_seconds=settings.worker_chunk_delay_seconds,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        jobs_to_enqueue = job_state.restore_incomplete_jobs(
            requeue_submitting_only=settings.queue_backend == "sqs"
        )

        for job_id in jobs_to_enqueue:
            await job_queue.enqueue(job_id)

        worker.start()
        try:
            yield
        finally:
            await worker.stop()

    app = FastAPI(title="Cassian", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.job_state = job_state
    app.state.job_queue = job_queue

    app.include_router(health_router)
    app.include_router(system_router)
    app.include_router(jobs_router)

    return app


app = create_app()
