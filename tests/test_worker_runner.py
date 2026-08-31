import asyncio

import pytest

from cassian.infra.checkpoints import FileCheckpointStore
from cassian.infra.queueing import InMemoryJobQueue
from cassian.services.job_state import AppState
from cassian.workers.local_worker import LocalWorker


@pytest.mark.asyncio
async def test_worker_can_process_job_without_shared_app_memory(tmp_path) -> None:
    checkpoint_store = FileCheckpointStore(base_path=tmp_path / "checkpoints")

    api_state = AppState(checkpoint_store=checkpoint_store)
    created_job = api_state.create_job(total_records=100_000, chunk_size=50_000)
    api_state.mark_queued(created_job.job_id)

    worker_state = AppState(checkpoint_store=checkpoint_store)
    job_queue = InMemoryJobQueue()
    await job_queue.enqueue(created_job.job_id)

    worker = LocalWorker(
        state=worker_state,
        job_queue=job_queue,
        chunk_delay_seconds=0.01,
    )
    worker.start()

    final_job = None
    for _ in range(50):
        reader_state = AppState(checkpoint_store=checkpoint_store)
        final_job = reader_state.get_job(created_job.job_id)
        assert final_job is not None
        if final_job.status == "COMPLETED":
            break
        await asyncio.sleep(0.02)

    await worker.stop()

    assert final_job is not None
    assert final_job.status == "COMPLETED"
    assert final_job.processed_records == 100_000
    assert final_job.last_checkpoint_records == 100_000
