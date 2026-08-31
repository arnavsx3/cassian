import pytest

from cassian.controller.job_controller import JobController
from cassian.infra.checkpoints import FileCheckpointStore
from cassian.infra.queueing import InMemoryJobQueue
from cassian.services.job_state import AppState


@pytest.mark.asyncio
async def test_controller_submits_and_marks_job_queued(tmp_path) -> None:
    checkpoint_store = FileCheckpointStore(base_path=tmp_path / "checkpoints")
    job_queue = InMemoryJobQueue()
    controller = JobController(
        state=AppState(checkpoint_store=checkpoint_store),
        job_queue=job_queue,
    )

    job = await controller.submit_job(total_records=100_000, chunk_size=50_000)

    assert job.status == "QUEUED"
    stored_job = checkpoint_store.load_job(job.job_id)
    assert stored_job is not None
    assert stored_job.status == "QUEUED"


@pytest.mark.asyncio
async def test_controller_requeues_recoverable_jobs_for_memory_queue(tmp_path) -> None:
    checkpoint_store = FileCheckpointStore(base_path=tmp_path / "checkpoints")
    state = AppState(checkpoint_store=checkpoint_store)

    job = state.create_job(total_records=150_000, chunk_size=50_000)
    job.processed_records = 50_000
    job.last_checkpoint_records = 50_000
    job.progress_percent = 33.33
    checkpoint_store.save_job(job)

    job_queue = InMemoryJobQueue()
    controller = JobController(
        state=AppState(checkpoint_store=checkpoint_store),
        job_queue=job_queue,
    )

    await controller.restore_jobs(requeue_submitting_only=False)

    message = await job_queue.receive()
    assert message is not None
    assert message.job_id == job.job_id
