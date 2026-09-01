from io import BytesIO

import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber

from cassian.domain.models import JobStatus, JobView
from cassian.infra.checkpoints import S3CheckpointStore


def test_s3_checkpoint_store_round_trip() -> None:
    client = boto3.client("s3", region_name="ap-south-1")
    store = S3CheckpointStore(
        bucket="cassian-checkpoints",
        prefix="cassian/checkpoints",
        client=client,
    )

    job = JobView(
        job_id="JOB-TEST1234",
        status=JobStatus.RECOVERING,
        total_records=150_000,
        chunk_size=50_000,
        processed_records=50_000,
        progress_percent=33.33,
        last_checkpoint_records=50_000,
        recovery_count=1,
        checkpoint_count=1,
        result_checksum=123456,
        worker_instance_id=None,
        worker_instance_type=None,
        worker_market_type=None,
        required_vcpus=2,
        required_memory_gib=4.0,
        estimated_runtime_hours=6.0,
        checkpoint_interval_hours=0.5,
    )
    payload = job.model_dump_json(indent=2)

    with Stubber(client) as stubber:
        stubber.add_response(
            "put_object",
            {"ETag": '"etag-1"'},
            {
                "Bucket": "cassian-checkpoints",
                "Key": "cassian/checkpoints/JOB-TEST1234.json",
                "Body": payload.encode("utf-8"),
                "ContentType": "application/json",
                "IfNoneMatch": "*",
            },
        )
        stubber.add_response(
            "get_object",
            {
                "Body": StreamingBody(BytesIO(payload.encode("utf-8")), len(payload)),
                "ETag": '"etag-1"',
            },
            {
                "Bucket": "cassian-checkpoints",
                "Key": "cassian/checkpoints/JOB-TEST1234.json",
            },
        )

        stored_job = store.save_job(job)
        loaded_job = store.load_job(job.job_id)

    assert stored_job.storage_etag == '"etag-1"'
    assert loaded_job is not None
    assert loaded_job.storage_etag == '"etag-1"'
    assert loaded_job.job_id == job.job_id
    assert loaded_job.processed_records == 50_000
