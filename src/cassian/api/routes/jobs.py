from fastapi import APIRouter, HTTPException, Request

from cassian.domain.models import JobCreate, JobView

router = APIRouter(tags=["jobs"])


@router.post("/jobs", response_model=JobView, status_code=201)
async def create_job(request: Request, payload: JobCreate) -> JobView:
    controller = request.app.state.job_controller

    try:
        return await controller.submit_job(
            total_records=payload.total_records,
            chunk_size=payload.chunk_size,
            required_vcpus=payload.required_vcpus,
            required_memory_gib=payload.required_memory_gib,
            estimated_runtime_hours=payload.estimated_runtime_hours,
            checkpoint_interval_hours=payload.checkpoint_interval_hours,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Failed to dispatch job to a worker.",
        ) from exc


@router.get("/jobs", response_model=list[JobView])
async def list_jobs(request: Request) -> list[JobView]:
    return request.app.state.job_controller.list_jobs()


@router.get("/jobs/{job_id}", response_model=JobView)
async def get_job(request: Request, job_id: str) -> JobView:
    job = request.app.state.job_controller.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
