import asyncio

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from cassian.app import create_app
from cassian.domain.models import JobStatus
from cassian.infra.checkpoints import FileCheckpointStore


class FailingJobQueue:
    async def enqueue(self, job_id: str) -> None:
        raise RuntimeError(f"queue unavailable for {job_id}")

    async def receive(self):
        await asyncio.sleep(3600)

    async def ack(self, message) -> None:
        return None


@pytest.mark.asyncio
async def test_failed_submission_does_not_leave_a_queued_job(tmp_path) -> None:
    checkpoint_store = FileCheckpointStore(base_path=tmp_path / "checkpoints")
    app = create_app(
        checkpoint_store=checkpoint_store,
        job_queue=FailingJobQueue(),
    )

    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/jobs",
                json={"total_records": 100_000, "chunk_size": 50_000},
            )

    assert response.status_code == 503

    jobs = checkpoint_store.load_all_jobs()
    assert len(jobs) == 1
    assert jobs[0].status == JobStatus.SUBMITTING
    assert jobs[0].processed_records == 0
