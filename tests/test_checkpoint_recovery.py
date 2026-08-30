import asyncio

import pytest

from cassian.models import JobStatus, JobView
from cassian.state import AppState
from cassian.storage import CheckpointStore
from cassian.worker import LocalWorker


@pytest.mark.asyncio
async def test_job_recovers_from_latest_checkpoint(tmp_path) -> None:
    checkpoint_store = CheckpointStore(base_path=tmp_path)

    first_state = AppState(checkpoint_store=checkpoint_store)
    first_worker = LocalWorker(state=first_state, chunk_delay_seconds=1.0)

    job = JobView.new(total_records=150_000, chunk_size=50_000)
    await first_state.submit_job(job)

    first_worker.start()
    await asyncio.sleep(0.1)
    await first_worker.stop()

    checkpointed_job = checkpoint_store.load_job(job.job_id)
    assert checkpointed_job is not None
    assert checkpointed_job.processed_records == 50_000
    assert checkpointed_job.last_checkpoint_records == 50_000

    recovered_state = AppState(checkpoint_store=checkpoint_store)
    recovered_state.restore_incomplete_jobs()

    recovered_job = recovered_state.get_job(job.job_id)
    assert recovered_job is not None
    assert recovered_job.status == JobStatus.RECOVERING
    assert recovered_job.recovery_count == 1
    assert recovered_job.processed_records == 50_000

    recovered_worker = LocalWorker(state=recovered_state, chunk_delay_seconds=0.01)
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
    assert final_job.recovery_count == 1
