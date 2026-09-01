from pathlib import Path
from typing import Protocol

from botocore.exceptions import ClientError

from cassian.core.aws import build_s3_client
from cassian.core.config import Settings
from cassian.domain.models import JobView


class CheckpointConflictError(RuntimeError):
    """Raised when a newer checkpoint already exists."""


class CheckpointStore(Protocol):
    def save_job(self, job: JobView) -> JobView: ...

    def load_job(self, job_id: str) -> JobView | None: ...

    def load_all_jobs(self) -> list[JobView]: ...


class FileCheckpointStore:
    def __init__(self, base_path: Path | None = None) -> None:
        self.base_path = base_path or Path("data/checkpoints")
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save_job(self, job: JobView) -> JobView:
        path = self.base_path / f"{job.job_id}.json"
        path.write_text(job.model_dump_json(indent=2), encoding="utf-8")
        return job

    def load_job(self, job_id: str) -> JobView | None:
        path = self.base_path / f"{job_id}.json"
        if not path.exists():
            return None
        return JobView.model_validate_json(path.read_text(encoding="utf-8"))

    def load_all_jobs(self) -> list[JobView]:
        jobs: list[JobView] = []
        for path in sorted(self.base_path.glob("*.json")):
            jobs.append(JobView.model_validate_json(path.read_text(encoding="utf-8")))
        return jobs


class S3CheckpointStore:
    def __init__(
        self,
        bucket: str,
        prefix: str = "cassian/checkpoints",
        client=None,
    ) -> None:
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = client

    def save_job(self, job: JobView) -> JobView:
        request = {
            "Bucket": self.bucket,
            "Key": self._key(job.job_id),
            "Body": job.model_dump_json(indent=2).encode("utf-8"),
            "ContentType": "application/json",
        }

        if job.storage_etag is None:
            request["IfNoneMatch"] = "*"
        else:
            request["IfMatch"] = job.storage_etag

        try:
            response = self.client.put_object(**request)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {
                "409",
                "412",
                "ConditionalRequestConflict",
                "PreconditionFailed",
            }:
                raise CheckpointConflictError(
                    f"Checkpoint changed concurrently for job {job.job_id}"
                ) from exc
            raise

        return job.model_copy(update={"storage_etag": response["ETag"]})

    def load_job(self, job_id: str) -> JobView | None:
        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=self._key(job_id),
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

        payload = response["Body"].read().decode("utf-8")
        job = JobView.model_validate_json(payload)
        return job.model_copy(update={"storage_etag": response["ETag"]})

    def load_all_jobs(self) -> list[JobView]:
        jobs: list[JobView] = []
        paginator = self.client.get_paginator("list_objects_v2")

        for page in paginator.paginate(
            Bucket=self.bucket,
            Prefix=self._prefix_with_slash(),
        ):
            for item in page.get("Contents", []):
                response = self.client.get_object(
                    Bucket=self.bucket,
                    Key=item["Key"],
                )
                payload = response["Body"].read().decode("utf-8")
                job = JobView.model_validate_json(payload)
                jobs.append(job.model_copy(update={"storage_etag": response["ETag"]}))

        return jobs

    def _key(self, job_id: str) -> str:
        if not self.prefix:
            return f"{job_id}.json"
        return f"{self.prefix}/{job_id}.json"

    def _prefix_with_slash(self) -> str:
        if not self.prefix:
            return ""
        return f"{self.prefix}/"


def build_checkpoint_store(settings: Settings) -> CheckpointStore:
    if settings.checkpoint_backend == "filesystem":
        return FileCheckpointStore(base_path=settings.checkpoint_dir)

    if not settings.s3_checkpoint_bucket:
        raise ValueError("S3_CHECKPOINT_BUCKET is required when CHECKPOINT_BACKEND=s3")

    s3_client = build_s3_client(settings)
    return S3CheckpointStore(
        bucket=settings.s3_checkpoint_bucket,
        prefix=settings.s3_checkpoint_prefix,
        client=s3_client,
    )
