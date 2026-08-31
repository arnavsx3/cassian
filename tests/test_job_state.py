from cassian.infra.checkpoints import FileCheckpointStore
from cassian.services.job_state import AppState


def test_list_jobs_reads_from_checkpoint_store(tmp_path) -> None:
    checkpoint_store = FileCheckpointStore(base_path=tmp_path / "checkpoints")

    writer_state = AppState(checkpoint_store=checkpoint_store)
    created_job = writer_state.create_job(total_records=100_000, chunk_size=50_000)
    writer_state.mark_queued(created_job.job_id)

    reader_state = AppState(checkpoint_store=checkpoint_store)
    jobs = reader_state.list_jobs()

    assert len(jobs) == 1
    assert jobs[0].job_id == created_job.job_id
    assert jobs[0].status == "QUEUED"


def test_get_job_can_load_from_store_without_shared_memory(tmp_path) -> None:
    checkpoint_store = FileCheckpointStore(base_path=tmp_path / "checkpoints")

    writer_state = AppState(checkpoint_store=checkpoint_store)
    created_job = writer_state.create_job(total_records=100_000, chunk_size=50_000)
    writer_state.mark_queued(created_job.job_id)

    reader_state = AppState(checkpoint_store=checkpoint_store)
    loaded_job = reader_state.get_job(created_job.job_id)

    assert loaded_job is not None
    assert loaded_job.job_id == created_job.job_id
    assert loaded_job.status == "QUEUED"
