import asyncio
from datetime import timedelta

from cassian.runtime import build_runtime


async def run_controller() -> None:
    runtime = build_runtime()

    if runtime.settings.worker_execution_mode != "ec2":
        raise RuntimeError(
            "WORKER_EXECUTION_MODE=ec2 is required for the controller process"
        )

    stale_after = timedelta(seconds=runtime.settings.worker_heartbeat_timeout_seconds)

    while True:
        await runtime.job_controller.reconcile_stale_workers(stale_after=stale_after)
        await asyncio.sleep(runtime.settings.controller_reconcile_interval_seconds)


def main() -> None:
    try:
        asyncio.run(run_controller())
    except KeyboardInterrupt:
        pass
