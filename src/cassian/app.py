from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from cassian.models import JobCreate, JobView
from cassian.state import AppState
from cassian.worker import LocalWorker

state = AppState()
worker = LocalWorker(state=state)


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.restore_incomplete_jobs()
    worker.start()
    yield
    await worker.stop()


app = FastAPI(title="Cassian", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/jobs", response_model=JobView, status_code=201)
async def create_job(payload: JobCreate) -> JobView:
    job = JobView.new(
        total_records=payload.total_records,
        chunk_size=payload.chunk_size,
    )
    return await state.submit_job(job)


@app.get("/jobs", response_model=list[JobView])
async def list_jobs() -> list[JobView]:
    return state.list_jobs()


@app.get("/jobs/{job_id}", response_model=JobView)
async def get_job(job_id: str) -> JobView:
    job = state.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
