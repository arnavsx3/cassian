import asyncio
import contextlib

from cassian.models import JobStatus
from cassian.state import AppState


class LocalWorker:
    def __init__(self, state: AppState, chunk_delay_seconds: float = 0.05) -> None:
        self.state = state
        self.chunk_delay_seconds = chunk_delay_seconds
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
            job_id = await self.state.queue.get()
            self.state.mark_running(job_id)

            try:
                while True:
                    job = self.state.advance_job(job_id)
                    if job.status == JobStatus.COMPLETED:
                        break
                    await asyncio.sleep(self.chunk_delay_seconds)
            finally:
                self.state.queue.task_done()
