import json
from pathlib import Path

from cassian.models import JobView


class CheckpointStore:
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
