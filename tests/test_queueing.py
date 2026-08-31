import json

import pytest

from cassian.infra.queueing import InMemoryJobQueue, SqsJobQueue


class StubSqsClient:
    def __init__(self) -> None:
        self.deleted_receipt_handles: list[str] = []
        self.messages: list[dict[str, str]] = []

    def send_message(self, *, QueueUrl: str, MessageBody: str) -> None:
        payload = json.loads(MessageBody)
        self.messages.append(
            {
                "Body": json.dumps(payload),
                "ReceiptHandle": "receipt-1",
            }
        )

    def receive_message(
        self,
        *,
        QueueUrl: str,
        MaxNumberOfMessages: int,
        WaitTimeSeconds: int,
        VisibilityTimeout: int,
    ) -> dict:
        if not self.messages:
            return {}
        return {"Messages": [self.messages.pop(0)]}

    def delete_message(self, *, QueueUrl: str, ReceiptHandle: str) -> None:
        self.deleted_receipt_handles.append(ReceiptHandle)


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
    client = StubSqsClient()
    queue = SqsJobQueue(
        queue_url="https://sqs.ap-south-1.amazonaws.com/123/test",
        client=client,
    )

    await queue.enqueue("JOB-1234")
    message = await queue.receive()

    assert message is not None
    assert message.job_id == "JOB-1234"

    await queue.ack(message)
    assert client.deleted_receipt_handles == ["receipt-1"]
