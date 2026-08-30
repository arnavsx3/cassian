from io import BytesIO

import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber

from cassian.domain.models import JobStatus, JobView
from cassian.storage import S3CheckpointStore


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
    )
    payload = job.model_dump_json(indent=2)

    with Stubber(client) as stubber:
        stubber.add_response(
            "put_object",
            {},
            {
                "Bucket": "cassian-checkpoints",
                "Key": "cassian/checkpoints/JOB-TEST1234.json",
                "Body": payload.encode("utf-8"),
                "ContentType": "application/json",
            },
        )
        stubber.add_response(
            "get_object",
            {
                "Body": StreamingBody(BytesIO(payload.encode("utf-8")), len(payload)),
            },
            {
                "Bucket": "cassian-checkpoints",
                "Key": "cassian/checkpoints/JOB-TEST1234.json",
            },
        )

        store.save_job(job)
        loaded_job = store.load_job("JOB-TEST1234")

    assert loaded_job is not None
    assert loaded_job.job_id == job.job_id
    assert loaded_job.processed_records == 50_000
    assert loaded_job.last_checkpoint_records == 50_000
    assert loaded_job.recovery_count == 1
