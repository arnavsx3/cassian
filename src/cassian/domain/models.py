from enum import Enum
from uuid import uuid4
from datetime import datetime
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    SUBMITTING = "SUBMITTING"
    SUBMISSION_FAILED = "SUBMISSION_FAILED"
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
    checkpoint_count: int
    result_checksum: int
    worker_instance_id: str | None
    worker_instance_type: str | None
    worker_market_type: str | None
    worker_launch_requested_at: datetime | None = None
    worker_started_at: datetime | None = None
    worker_heartbeat_at: datetime | None = None
    worker_launch_attempts: int = 0

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
            checkpoint_count=0,
            result_checksum=0,
            worker_instance_id=None,
            worker_instance_type=None,
            worker_market_type=None,
        )
