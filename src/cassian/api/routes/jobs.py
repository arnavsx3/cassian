from fastapi import APIRouter, HTTPException, Request

from cassian.domain.models import JobCreate, JobView

router = APIRouter(tags=["jobs"])


@router.post("/jobs", response_model=JobView, status_code=201)
async def create_job(request: Request, payload: JobCreate) -> JobView:
    job_state = request.app.state.job_state
    job_queue = request.app.state.job_queue

    job = job_state.create_job(
        total_records=payload.total_records,
        chunk_size=payload.chunk_size,
    )

    try:
        await job_queue.enqueue(job.job_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Failed to dispatch job to the queue.",
        ) from exc

    return job_state.mark_queued(job.job_id)


@router.get("/jobs", response_model=list[JobView])
async def list_jobs(request: Request) -> list[JobView]:
    return request.app.state.job_state.list_jobs()


@router.get("/jobs/{job_id}", response_model=JobView)
async def get_job(request: Request, job_id: str) -> JobView:
    job = request.app.state.job_state.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
