import asyncio
import os

from cassian.runtime import build_runtime


async def run_worker() -> None:
    job_id = os.environ.get("CASSIAN_JOB_ID")
    if not job_id:
        raise RuntimeError("CASSIAN_JOB_ID is required for a standalone worker")

    runtime = build_runtime()
    await runtime.worker.process_job(job_id)


def main() -> None:
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        pass
