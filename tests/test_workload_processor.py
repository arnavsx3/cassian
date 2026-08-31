from cassian.domain.models import JobView
from cassian.workloads.processor import WorkloadProcessor


def test_processor_advances_job_in_chunks_and_preserves_checksum() -> None:
    processor = WorkloadProcessor()
    job = JobView.new(total_records=120_000, chunk_size=50_000)

    processor.process_chunk(job)
    assert job.processed_records == 50_000
    assert job.last_checkpoint_records == 50_000
    assert job.checkpoint_count == 1

    processor.process_chunk(job)
    assert job.processed_records == 100_000
    assert job.last_checkpoint_records == 100_000
    assert job.checkpoint_count == 2

    processor.process_chunk(job)
    assert job.processed_records == 120_000
    assert job.last_checkpoint_records == 120_000
    assert job.checkpoint_count == 3
    assert job.progress_percent == 100.0

    expected_checksum = processor.full_checksum(total_records=120_000)
    assert job.result_checksum == expected_checksum
