import asyncio

from cassian.runtime import build_runtime


async def run_worker() -> None:
    runtime = build_runtime()
    runtime.worker.start()

    try:
        await asyncio.Event().wait()
    finally:
        await runtime.worker.stop()


def main() -> None:
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        pass
