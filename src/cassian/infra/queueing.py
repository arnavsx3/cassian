import asyncio
import json
from dataclasses import dataclass
from typing import Protocol

import boto3


@dataclass(slots=True)
class QueueMessage:
    job_id: str
    receipt_handle: str | None = None


class JobQueue(Protocol):
    async def enqueue(self, job_id: str) -> None: ...
    async def receive(self) -> QueueMessage | None: ...
    async def ack(self, message: QueueMessage) -> None: ...


class InMemoryJobQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[QueueMessage] = asyncio.Queue()

    async def enqueue(self, job_id: str) -> None:
        await self._queue.put(QueueMessage(job_id=job_id))

    async def receive(self) -> QueueMessage | None:
        return await self._queue.get()

    async def ack(self, message: QueueMessage) -> None:
        return None


class SqsJobQueue:
    def __init__(
        self,
        queue_url: str,
        region_name: str,
        wait_time_seconds: int = 5,
        visibility_timeout: int = 120,
        client=None,
    ) -> None:
        self.queue_url = queue_url
        self.wait_time_seconds = wait_time_seconds
        self.visibility_timeout = visibility_timeout
        self.client = client or boto3.client("sqs", region_name=region_name)

    async def enqueue(self, job_id: str) -> None:
        await asyncio.to_thread(
            self.client.send_message,
            QueueUrl=self.queue_url,
            MessageBody=json.dumps({"job_id": job_id}),
        )

    async def receive(self) -> QueueMessage | None:
        response = await asyncio.to_thread(
            self.client.receive_message,
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=self.wait_time_seconds,
            VisibilityTimeout=self.visibility_timeout,
        )

        messages = response.get("Messages", [])
        if not messages:
            return None

        raw_message = messages[0]
        payload = json.loads(raw_message["Body"])
        return QueueMessage(
            job_id=payload["job_id"],
            receipt_handle=raw_message["ReceiptHandle"],
        )

    async def ack(self, message: QueueMessage) -> None:
        if message.receipt_handle is None:
            return

        await asyncio.to_thread(
            self.client.delete_message,
            QueueUrl=self.queue_url,
            ReceiptHandle=message.receipt_handle,
        )
