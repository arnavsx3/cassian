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
        self.dispatched_decisions: list[PlacementDecision] = []

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
        decision = PlacementDecision(
            strategy=PlacementStrategyName.RISK_AWARE,
            market_type=WorkerMarketType.SPOT,
            profile=profile,
            cost_estimate=CostEstimate(
                base_compute_cost=0.18,
                interruption_probability=0.05,
                expected_recovery_cost=0.5,
                expected_total_cost=0.68,
            ),
        )
        return PlacementSelection(
            decision=decision,
            source="strategy",
        )

    def dispatch(
        self,
        *,
        job_id: str,
        worker_generation: int,
        decision: PlacementDecision,
    ) -> WorkerLaunchResult:
        self.dispatched_decisions.append(decision)
        return WorkerLaunchResult(
            instance_id="i-1234567890abcdef0",
            instance_type=decision.profile.instance_type,
            market_type=decision.market_type.value,
        )

    def terminate(self, *, instance_id: str) -> None:
        return None


@pytest.mark.asyncio
async def test_controller_submits_and_marks_job_queued(tmp_path) -> None:
    checkpoint_store = FileCheckpointStore(base_path=tmp_path / "checkpoints")
    job_queue = InMemoryJobQueue()
    controller = JobController(
        state=AppState(checkpoint_store=checkpoint_store),
        job_queue=job_queue,
    )

    job = await controller.submit_job(
        total_records=100_000,
        chunk_size=50_000,
        required_vcpus=2,
        required_memory_gib=4.0,
        estimated_runtime_hours=6.0,
        checkpoint_interval_hours=0.5,
    )

    assert job.status == "QUEUED"
    stored_job = checkpoint_store.load_job(job.job_id)
    assert stored_job is not None
    assert stored_job.status == "QUEUED"


@pytest.mark.asyncio
async def test_controller_persists_placement_before_ec2_launch(tmp_path) -> None:
    checkpoint_store = FileCheckpointStore(base_path=tmp_path / "checkpoints")
    dispatcher = StubWorkerDispatcher()
    controller = JobController(
        state=AppState(checkpoint_store=checkpoint_store),
        job_queue=InMemoryJobQueue(),
        worker_dispatcher=dispatcher,
        enqueue_jobs=False,
    )

    job = await controller.submit_job(
        total_records=100_000,
        chunk_size=50_000,
        required_vcpus=2,
        required_memory_gib=4.0,
        estimated_runtime_hours=6.0,
        checkpoint_interval_hours=0.5,
    )

    assert job.worker_instance_id == "i-1234567890abcdef0"
    assert job.worker_instance_type == "c6i.large"
    assert job.worker_market_type == "spot"
    assert job.worker_generation == 1
    assert job.worker_launch_attempts == 1
    assert job.placement_strategy == "RISK_AWARE"
    assert job.placement_source == "strategy"
    assert job.placement_instance_type == "c6i.large"
    assert job.placement_market_type == "spot"
    assert job.placement_expected_total_cost == 0.68
    assert job.placement_interruption_probability == 0.05
    assert dispatcher.dispatched_decisions[0].profile.instance_type == "c6i.large"


@pytest.mark.asyncio
async def test_controller_requeues_recoverable_jobs_for_memory_queue(tmp_path) -> None:
    checkpoint_store = FileCheckpointStore(base_path=tmp_path / "checkpoints")
    state = AppState(checkpoint_store=checkpoint_store)

    job = state.create_job(total_records=150_000, chunk_size=50_000)
    job.processed_records = 50_000
    job.last_checkpoint_records = 50_000
    job.progress_percent = 33.33
    checkpoint_store.save_job(job)

    job_queue = InMemoryJobQueue()
    controller = JobController(
        state=AppState(checkpoint_store=checkpoint_store),
        job_queue=job_queue,
    )

    await controller.restore_jobs(requeue_submitting_only=False)

    message = await job_queue.receive()
    assert message is not None
    assert message.job_id == job.job_id
