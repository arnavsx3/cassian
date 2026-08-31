import asyncio

import pytest

from cassian.domain.models import JobStatus
from cassian.infra.checkpoints import FileCheckpointStore
from cassian.infra.queueing import InMemoryJobQueue
from cassian.services.job_state import AppState
from cassian.workers.local_worker import LocalWorker


@pytest.mark.asyncio
async def test_job_recovers_from_latest_checkpoint(tmp_path) -> None:
    checkpoint_store = FileCheckpointStore(base_path=tmp_path)
    first_queue = InMemoryJobQueue()
    first_state = AppState(checkpoint_store=checkpoint_store)
    first_worker = LocalWorker(
        state=first_state,
        job_queue=first_queue,
        chunk_delay_seconds=1.0,
    )

    job = first_state.create_job(total_records=150_000, chunk_size=50_000)
    first_state.mark_queued(job.job_id)
    await first_queue.enqueue(job.job_id)

    first_worker.start()
    await asyncio.sleep(0.1)
    await first_worker.stop()

    checkpointed_job = checkpoint_store.load_job(job.job_id)
    assert checkpointed_job is not None
    assert checkpointed_job.processed_records == 50_000
    assert checkpointed_job.last_checkpoint_records == 50_000
    assert checkpointed_job.checkpoint_count == 1
    assert checkpointed_job.result_checksum > 0

    recovered_queue = InMemoryJobQueue()
    recovered_state = AppState(checkpoint_store=checkpoint_store)

    for job_id in recovered_state.restore_incomplete_jobs(
        requeue_submitting_only=False
    ):
        await recovered_queue.enqueue(job_id)

    recovered_job = recovered_state.get_job(job.job_id)
    assert recovered_job is not None
    assert recovered_job.status == JobStatus.RECOVERING
    assert recovered_job.recovery_count == 1
    assert recovered_job.processed_records == 50_000

    recovered_worker = LocalWorker(
        state=recovered_state,
        job_queue=recovered_queue,
        chunk_delay_seconds=0.01,
    )
    recovered_worker.start()

    final_job = None
    for _ in range(50):
        current_job = recovered_state.get_job(job.job_id)
        assert current_job is not None
        final_job = current_job
        if current_job.status == JobStatus.COMPLETED:
            break
        await asyncio.sleep(0.02)

    await recovered_worker.stop()

    assert final_job is not None
    assert final_job.status == JobStatus.COMPLETED
    assert final_job.processed_records == 150_000
    assert final_job.last_checkpoint_records == 150_000
    assert final_job.checkpoint_count == 3
    assert final_job.result_checksum > checkpointed_job.result_checksum
    assert final_job.recovery_count == 1
