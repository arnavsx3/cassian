import asyncio
import contextlib

from cassian.domain.models import JobStatus
from cassian.infra.queueing import JobQueue
from cassian.services.job_state import AppState


class LocalWorker:
    def __init__(
        self,
        state: AppState,
        job_queue: JobQueue,
        chunk_delay_seconds: float = 0.05,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self.state = state
        self.job_queue = job_queue
        self.chunk_delay_seconds = chunk_delay_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        self._task = asyncio.create_task(self.run(), name="cassian-local-worker")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def process_job(self, job_id: str) -> None:
        self.state.mark_running(job_id)

        while True:
            job = self.state.advance_job(job_id)
            if job.status == JobStatus.COMPLETED:
                return
            await asyncio.sleep(self.chunk_delay_seconds)

    async def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                message = await asyncio.wait_for(
                    self.job_queue.receive(),
                    timeout=self.poll_interval_seconds,
                )
            except TimeoutError:
                continue

            if message is None:
                continue

            await self.process_job(message.job_id)
            await self.job_queue.ack(message)
