from pathlib import Path
from typing import Protocol

import boto3
from botocore.exceptions import ClientError

from cassian.config import Settings
from cassian.models import JobView


class CheckpointStore(Protocol):
    def save_job(self, job: JobView) -> None: ...

    def load_job(self, job_id: str) -> JobView | None: ...

    def load_all_jobs(self) -> list[JobView]: ...


class FileCheckpointStore:
    def __init__(self, base_path: Path | None = None) -> None:
        self.base_path = base_path or Path("data/checkpoints")
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save_job(self, job: JobView) -> None:
        path = self.base_path / f"{job.job_id}.json"
        path.write_text(job.model_dump_json(indent=2), encoding="utf-8")

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
        self.client = client or boto3.client("s3")

    def save_job(self, job: JobView) -> None:
        payload = job.model_dump_json(indent=2).encode("utf-8")
        self.client.put_object(
            Bucket=self.bucket,
            Key=self._key(job.job_id),
            Body=payload,
            ContentType="application/json",
        )

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
        return JobView.model_validate_json(payload)

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
                jobs.append(JobView.model_validate_json(payload))

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

    if not settings.aws_region:
        raise ValueError("AWS_REGION is required when CHECKPOINT_BACKEND=s3")

    if not settings.s3_checkpoint_bucket:
        raise ValueError("S3_CHECKPOINT_BUCKET is required when CHECKPOINT_BACKEND=s3")

    s3_client = boto3.client("s3", region_name=settings.aws_region)
    return S3CheckpointStore(
        bucket=settings.s3_checkpoint_bucket,
        prefix=settings.s3_checkpoint_prefix,
        client=s3_client,
    )
