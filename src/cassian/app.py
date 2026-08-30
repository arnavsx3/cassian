from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from cassian.config import Settings, get_settings
from cassian.models import JobCreate, JobView
from cassian.queueing import InMemoryJobQueue, JobQueue, SqsJobQueue
from cassian.state import AppState
from cassian.storage import CheckpointStore, build_checkpoint_store
from cassian.worker import LocalWorker


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
    state = AppState(checkpoint_store=checkpoint_store)
    worker = LocalWorker(
        state=state,
        job_queue=job_queue,
        chunk_delay_seconds=settings.worker_chunk_delay_seconds,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        jobs_to_requeue = state.restore_incomplete_jobs()

        if settings.queue_backend == "memory":
            for job_id in jobs_to_requeue:
                await job_queue.enqueue(job_id)

        worker.start()
        yield
        await worker.stop()

    app = FastAPI(title="Cassian", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.state = state
    app.state.job_queue = job_queue

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/system/queue")
    async def queue_config(request: Request) -> dict[str, str]:
        return {"backend": request.app.state.settings.queue_backend}

    @app.post("/jobs", response_model=JobView, status_code=201)
    async def create_job(request: Request, payload: JobCreate) -> JobView:
        job = JobView.new(
            total_records=payload.total_records,
            chunk_size=payload.chunk_size,
        )
        request.app.state.state.register_job(job)
        await request.app.state.job_queue.enqueue(job.job_id)
        return job

    @app.get("/jobs", response_model=list[JobView])
    async def list_jobs(request: Request) -> list[JobView]:
        return request.app.state.state.list_jobs()

    @app.get("/jobs/{job_id}", response_model=JobView)
    async def get_job(request: Request, job_id: str) -> JobView:
        job = request.app.state.state.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    return app


app = create_app()
