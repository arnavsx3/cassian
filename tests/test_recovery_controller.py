from datetime import UTC, datetime, timedelta

import pytest

from cassian.controller.ec2_launcher import WorkerLaunchResult
from cassian.controller.job_controller import JobController
from cassian.infra.checkpoints import FileCheckpointStore
from cassian.infra.queueing import InMemoryJobQueue
from cassian.services.job_state import AppState


class StubWorkerDispatcher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def dispatch(self, *, job_id: str) -> WorkerLaunchResult:
        self.calls.append(job_id)
        return WorkerLaunchResult(
            instance_id="i-replacement",
            instance_type="t3.micro",
            market_type="spot",
        )


@pytest.mark.asyncio
async def test_controller_relaunches_stale_ec2_worker(tmp_path) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    checkpoint_store = FileCheckpointStore(base_path=tmp_path / "checkpoints")
    state = AppState(checkpoint_store=checkpoint_store)
    dispatcher = StubWorkerDispatcher()

    job = state.create_job(total_records=100_000, chunk_size=50_000)
    state.mark_queued(job.job_id)
    state.request_worker_launch(
        job.job_id,
        now=now - timedelta(minutes=5),
    )
    state.attach_worker_launch(
        job.job_id,
        instance_id="i-old-worker",
        instance_type="t3.micro",
        market_type="spot",
    )

    controller = JobController(
        state=state,
        job_queue=InMemoryJobQueue(),
        worker_dispatcher=dispatcher,
        enqueue_jobs=False,
    )

    relaunched_jobs = await controller.reconcile_stale_workers(
        stale_after=timedelta(seconds=90),
        now=now,
    )

    assert dispatcher.calls == [job.job_id]
    assert len(relaunched_jobs) == 1
    assert relaunched_jobs[0].worker_instance_id == "i-replacement"
    assert relaunched_jobs[0].status == "RECOVERING"
    assert relaunched_jobs[0].recovery_count == 1


@pytest.mark.asyncio
async def test_controller_does_not_relaunch_worker_with_fresh_heartbeat(
    tmp_path,
) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    checkpoint_store = FileCheckpointStore(base_path=tmp_path / "checkpoints")
    state = AppState(checkpoint_store=checkpoint_store)
    dispatcher = StubWorkerDispatcher()

    job = state.create_job(total_records=100_000, chunk_size=50_000)
    state.mark_queued(job.job_id)
    state.request_worker_launch(job.job_id, now=now - timedelta(minutes=5))
    state.mark_running(job.job_id)
    state.record_worker_heartbeat(job.job_id, now=now - timedelta(seconds=30))

    controller = JobController(
        state=state,
        job_queue=InMemoryJobQueue(),
        worker_dispatcher=dispatcher,
        enqueue_jobs=False,
    )

    relaunched_jobs = await controller.reconcile_stale_workers(
        stale_after=timedelta(seconds=90),
        now=now,
    )

    assert relaunched_jobs == []
    assert dispatcher.calls == []
