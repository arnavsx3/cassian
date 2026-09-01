from cassian.domain.models import JobView
from cassian.infra.checkpoints import CheckpointStore


class JobRepository:
    def __init__(self, checkpoint_store: CheckpointStore) -> None:
        self.checkpoint_store = checkpoint_store

    def create(self, job: JobView) -> JobView:
        return self.checkpoint_store.save_job(job)

    def save(self, job: JobView) -> JobView:
        return self.checkpoint_store.save_job(job)

    def get(self, job_id: str) -> JobView | None:
        return self.checkpoint_store.load_job(job_id)

    def list(self) -> list[JobView]:
        return self.checkpoint_store.load_all_jobs()
