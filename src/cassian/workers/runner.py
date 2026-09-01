import asyncio
import os

from cassian.runtime import build_runtime


async def run_worker() -> None:
    job_id = os.environ.get("CASSIAN_JOB_ID")
    if not job_id:
        raise RuntimeError("CASSIAN_JOB_ID is required for a standalone worker")

    generation_value = os.environ.get("CASSIAN_WORKER_GENERATION")
    if generation_value is None:
        raise RuntimeError("CASSIAN_WORKER_GENERATION is required")

    try:
        worker_generation = int(generation_value)
    except ValueError as exc:
        raise RuntimeError("CASSIAN_WORKER_GENERATION must be an integer") from exc

    runtime = build_runtime()
    await runtime.worker.process_job(
        job_id,
        worker_generation=worker_generation,
    )


def main() -> None:
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        pass
