from dataclasses import dataclass
from typing import Literal, Protocol

from cassian.controller.ec2_launcher import Ec2WorkerLauncher, WorkerLaunchResult
from cassian.core.config import Settings
from cassian.domain.models import JobView
from cassian.placement.catalog import get_spot_pool_profiles
from cassian.placement.cost_model import (
    estimate_on_demand_job_cost,
    estimate_spot_job_cost,
)
from cassian.placement.eligibility import require_eligible_profiles
from cassian.placement.models import (
    CostEstimate,
    PlacementDecision,
    PlacementStrategyName,
    RecoveryCostModel,
    SpotPoolProfile,
    WorkerMarketType,
    WorkloadRequirements,
)
from cassian.placement.strategies import get_strategy


@dataclass(frozen=True, slots=True)
class PlacementSelection:
    decision: PlacementDecision
    source: Literal["strategy", "instance_type_override"]


class WorkerDispatchPort(Protocol):
    def select_placement(self, *, job: JobView) -> PlacementSelection: ...

    def dispatch(
        self,
        *,
        job_id: str,
        worker_generation: int,
        decision: PlacementDecision,
    ) -> WorkerLaunchResult | None: ...

    def terminate(self, *, instance_id: str) -> None: ...


class WorkerDispatcher:
    def __init__(
        self,
        settings: Settings,
        ec2_launcher: Ec2WorkerLauncher | None = None,
    ) -> None:
        self.settings = settings
        self.ec2_launcher = ec2_launcher

    def select_placement(self, *, job: JobView) -> PlacementSelection:
        if not self.settings.aws_region:
            raise ValueError("AWS_REGION is required for placement selection")

        workload = WorkloadRequirements(
            required_vcpus=job.required_vcpus,
            required_memory_gib=job.required_memory_gib,
            estimated_runtime_hours=job.estimated_runtime_hours,
        )
        profiles = get_spot_pool_profiles(region=self.settings.aws_region)
        strategy_name = PlacementStrategyName(self.settings.placement_strategy)
        recovery_cost_model = RecoveryCostModel(
            checkpoint_recovery_cost=(self.settings.placement_checkpoint_recovery_cost),
            relaunch_cost=self.settings.placement_relaunch_cost,
        )
        decision = get_strategy(strategy_name).select(
            profiles=profiles,
            workload=workload,
            recovery_cost_model=recovery_cost_model,
        )

        if self.settings.ec2_worker_instance_type_override is None:
            return PlacementSelection(
                decision=decision,
                source="strategy",
            )

        override_profile = self._get_override_profile(
            profiles=profiles,
            workload=workload,
        )
        return PlacementSelection(
            decision=self._build_override_decision(
                strategy_name=strategy_name,
                profile=override_profile,
                workload=workload,
                recovery_cost_model=recovery_cost_model,
            ),
            source="instance_type_override",
        )

    def dispatch(
        self,
        *,
        job_id: str,
        worker_generation: int,
        decision: PlacementDecision,
    ) -> WorkerLaunchResult | None:
        if self.settings.worker_execution_mode == "local":
            return None

        if self.settings.worker_execution_mode == "ec2":
            if self.ec2_launcher is None:
                raise ValueError("EC2 launcher is not configured")

            return self.ec2_launcher.launch_worker(
                job_id=job_id,
                worker_generation=worker_generation,
                instance_type=decision.profile.instance_type,
                market_type=decision.market_type,
                placement_strategy=decision.strategy,
            )

        raise ValueError(
            f"Unsupported WORKER_EXECUTION_MODE: {self.settings.worker_execution_mode}"
        )

    def terminate(self, *, instance_id: str) -> None:
        if self.settings.worker_execution_mode == "local":
            return

        if self.ec2_launcher is None:
            raise ValueError("EC2 launcher is not configured")

        self.ec2_launcher.terminate_worker(instance_id=instance_id)

    def _get_override_profile(
        self,
        *,
        profiles: list[SpotPoolProfile],
        workload: WorkloadRequirements,
    ) -> SpotPoolProfile:
        override = self.settings.ec2_worker_instance_type_override
        if override is None:
            raise RuntimeError("Instance type override is not configured")

        eligible_profiles = require_eligible_profiles(
            profiles=profiles,
            workload=workload,
        )

        for profile in eligible_profiles:
            if profile.instance_type == override:
                return profile

        raise ValueError(
            "EC2_WORKER_INSTANCE_TYPE_OVERRIDE must be an eligible instance "
            "type from the configured placement catalog"
        )

    def _build_override_decision(
        self,
        *,
        strategy_name: PlacementStrategyName,
        profile: SpotPoolProfile,
        workload: WorkloadRequirements,
        recovery_cost_model: RecoveryCostModel,
    ) -> PlacementDecision:
        if strategy_name == PlacementStrategyName.ON_DEMAND:
            on_demand_cost = estimate_on_demand_job_cost(
                profile=profile,
                workload=workload,
            )
            return PlacementDecision(
                strategy=strategy_name,
                market_type=WorkerMarketType.ON_DEMAND,
                profile=profile,
                cost_estimate=CostEstimate(
                    base_compute_cost=on_demand_cost,
                    interruption_probability=0.0,
                    expected_recovery_cost=0.0,
                    expected_total_cost=on_demand_cost,
                ),
            )

        return PlacementDecision(
            strategy=strategy_name,
            market_type=WorkerMarketType.SPOT,
            profile=profile,
            cost_estimate=estimate_spot_job_cost(
                profile=profile,
                workload=workload,
                recovery_cost_model=recovery_cost_model,
            ),
        )
