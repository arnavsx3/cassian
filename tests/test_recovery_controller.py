from datetime import UTC, datetime, timedelta

import pytest

from cassian.controller.ec2_launcher import WorkerLaunchResult
from cassian.controller.job_controller import JobController
from cassian.controller.worker_dispatcher import PlacementSelection
from cassian.infra.checkpoints import FileCheckpointStore
from cassian.infra.queueing import InMemoryJobQueue
from cassian.placement.models import (
    CostEstimate,
    PlacementDecision,
    PlacementStrategyName,
    SpotPoolProfile,
    WorkerMarketType,
)
from cassian.services.job_state import AppState


class StubWorkerDispatcher:
    def __init__(self) -> None:
        self.dispatch_calls: list[tuple[str, int]] = []
        self.terminate_calls: list[str] = []

    def select_placement(self, *, job) -> PlacementSelection:
        profile = SpotPoolProfile(
            instance_type="c6i.large",
            region="ap-south-1",
            vcpus=job.required_vcpus,
            memory_gib=job.required_memory_gib,
            spot_price_per_hour=0.03,
            on_demand_price_per_hour=0.09,
            interruption_probability_per_hour=0.01,
        )
        return PlacementSelection(
            decision=PlacementDecision(
                strategy=PlacementStrategyName.RISK_AWARE,
                market_type=WorkerMarketType.SPOT,
                profile=profile,
                cost_estimate=CostEstimate(
                    base_compute_cost=0.18,
                    interruption_probability=0.05,
                    expected_recovery_cost=0.5,
                    expected_total_cost=0.68,
                ),
            ),
            source="strategy",
        )

    def dispatch(
        self,
        *,
        job_id: str,
        worker_generation: int,
        decision: PlacementDecision,
    ) -> WorkerLaunchResult:
        self.dispatch_calls.append((job_id, worker_generation))
        return WorkerLaunchResult(
            instance_id="i-new-worker",
            instance_type=decision.profile.instance_type,
            market_type=decision.market_type.value,
        )

    def terminate(self, *, instance_id: str) -> None:
        self.terminate_calls.append(instance_id)


@pytest.mark.asyncio
async def test_controller_terminates_and_relaunches_stale_worker(tmp_path) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    checkpoint_store = FileCheckpointStore(base_path=tmp_path / "checkpoints")
    state = AppState(checkpoint_store=checkpoint_store)
    dispatcher = StubWorkerDispatcher()

    job = state.create_job(total_records=100_000, chunk_size=50_000)
    state.mark_queued(job.job_id)
    first_launch = state.request_worker_launch(
        job.job_id,
        max_attempts=3,
        now=now - timedelta(minutes=5),
    )
    state.attach_worker_launch(
        job.job_id,
        worker_generation=first_launch.worker_generation,
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

    assert dispatcher.terminate_calls == ["i-old-worker"]
    assert dispatcher.dispatch_calls == [(job.job_id, 2)]
    assert len(relaunched_jobs) == 1
    assert relaunched_jobs[0].worker_instance_id == "i-new-worker"
    assert relaunched_jobs[0].worker_generation == 2
    assert relaunched_jobs[0].recovery_count == 1


@pytest.mark.asyncio
async def test_controller_does_not_relaunch_fresh_worker(tmp_path) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    checkpoint_store = FileCheckpointStore(base_path=tmp_path / "checkpoints")
    state = AppState(checkpoint_store=checkpoint_store)
    dispatcher = StubWorkerDispatcher()

    job = state.create_job(total_records=100_000, chunk_size=50_000)
    state.mark_queued(job.job_id)
    first_launch = state.request_worker_launch(
        job.job_id,
        max_attempts=3,
        now=now - timedelta(seconds=30),
    )
    state.attach_worker_launch(
        job.job_id,
        worker_generation=first_launch.worker_generation,
        instance_id="i-current-worker",
        instance_type="t3.micro",
        market_type="spot",
    )
    state.record_worker_heartbeat(
        job.job_id,
        worker_generation=first_launch.worker_generation,
        now=now - timedelta(seconds=30),
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

    assert relaunched_jobs == []
    assert dispatcher.terminate_calls == []
    assert dispatcher.dispatch_calls == []
