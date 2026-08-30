from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    SUBMITTING = "SUBMITTING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"


class JobCreate(BaseModel):
    total_records: int = Field(default=200_000, gt=0)
    chunk_size: int = Field(default=50_000, gt=0)


class JobView(BaseModel):
    job_id: str
    status: JobStatus
    total_records: int
    chunk_size: int
    processed_records: int
    progress_percent: float
    last_checkpoint_records: int
    recovery_count: int

    @classmethod
    def new(cls, total_records: int, chunk_size: int) -> "JobView":
        return cls(
            job_id=f"JOB-{uuid4().hex[:8].upper()}",
            status=JobStatus.SUBMITTING,
            total_records=total_records,
            chunk_size=chunk_size,
            processed_records=0,
            progress_percent=0.0,
            last_checkpoint_records=0,
            recovery_count=0,
        )
