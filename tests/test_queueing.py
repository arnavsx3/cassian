from io import BytesIO
import json

import boto3
import pytest
from botocore.stub import Stubber

from cassian.queueing import InMemoryJobQueue, SqsJobQueue


@pytest.mark.asyncio
async def test_in_memory_queue_round_trip() -> None:
    queue = InMemoryJobQueue()

    await queue.enqueue("JOB-1234")
    message = await queue.receive()

    assert message is not None
    assert message.job_id == "JOB-1234"

    await queue.ack(message)


@pytest.mark.asyncio
async def test_sqs_queue_round_trip() -> None:
    client = boto3.client("sqs", region_name="ap-south-1")
    queue = SqsJobQueue(
        queue_url="https://sqs.ap-south-1.amazonaws.com/123/test",
        region_name="ap-south-1",
        client=client,
    )

    with Stubber(client) as stubber:
        stubber.add_response(
            "send_message",
            {"MessageId": "msg-1"},
            {
                "QueueUrl": "https://sqs.ap-south-1.amazonaws.com/123/test",
                "MessageBody": json.dumps({"job_id": "JOB-1234"}),
            },
        )
        stubber.add_response(
            "receive_message",
            {
                "Messages": [
                    {
                        "Body": json.dumps({"job_id": "JOB-1234"}),
                        "ReceiptHandle": "receipt-1",
                        "MessageId": "msg-1",
                    }
                ]
            },
            {
                "QueueUrl": "https://sqs.ap-south-1.amazonaws.com/123/test",
                "MaxNumberOfMessages": 1,
                "WaitTimeSeconds": 5,
                "VisibilityTimeout": 120,
            },
        )
        stubber.add_response(
            "delete_message",
            {},
            {
                "QueueUrl": "https://sqs.ap-south-1.amazonaws.com/123/test",
                "ReceiptHandle": "receipt-1",
            },
        )

        await queue.enqueue("JOB-1234")
        message = await queue.receive()
        assert message is not None
        assert message.job_id == "JOB-1234"
        await queue.ack(message)
