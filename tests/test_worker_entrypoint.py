import pytest

from cassian.workers.runner import run_worker


@pytest.mark.asyncio
async def test_standalone_worker_requires_target_job_id(monkeypatch) -> None:
    monkeypatch.delenv("CASSIAN_JOB_ID", raising=False)

    with pytest.raises(RuntimeError, match="CASSIAN_JOB_ID"):
        await run_worker()
