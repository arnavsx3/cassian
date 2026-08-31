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

            self.state.mark_running(message.job_id)

            while True:
                job = self.state.advance_job(message.job_id)
                if job.status == JobStatus.COMPLETED:
                    await self.job_queue.ack(message)
                    break
                await asyncio.sleep(self.chunk_delay_seconds)
