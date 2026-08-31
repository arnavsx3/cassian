from contextlib import asynccontextmanager

from fastapi import FastAPI

from cassian.api.routes.health import router as health_router
from cassian.api.routes.jobs import router as jobs_router
from cassian.api.routes.system import router as system_router
from cassian.core.config import Settings
from cassian.infra.checkpoints import CheckpointStore
from cassian.infra.queueing import JobQueue
from cassian.runtime import build_runtime


def create_app(
    settings: Settings | None = None,
    checkpoint_store: CheckpointStore | None = None,
    job_queue: JobQueue | None = None,
) -> FastAPI:
    runtime = build_runtime(
        settings=settings,
        checkpoint_store=checkpoint_store,
        job_queue=job_queue,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await runtime.job_controller.restore_jobs(
            requeue_submitting_only=runtime.settings.queue_backend == "sqs"
        )

        should_start_embedded_worker = (
            runtime.settings.embedded_worker_enabled
            and runtime.settings.worker_execution_mode == "local"
        )

        if should_start_embedded_worker:
            runtime.worker.start()

        try:
            yield
        finally:
            if should_start_embedded_worker:
                await runtime.worker.stop()

    app = FastAPI(title="Cassian", version="0.1.0", lifespan=lifespan)
    app.state.settings = runtime.settings
    app.state.job_state = runtime.job_state
    app.state.job_queue = runtime.job_queue
    app.state.job_controller = runtime.job_controller

    app.include_router(health_router)
    app.include_router(system_router)
    app.include_router(jobs_router)

    return app


app = create_app()
