from collections.abc import Iterable

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


class CheapestStrategy:
    name = PlacementStrategyName.CHEAPEST

    def select(
        self,
        *,
        profiles: Iterable[SpotPoolProfile],
        workload: WorkloadRequirements,
        recovery_cost_model: RecoveryCostModel,
    ) -> PlacementDecision:
        eligible_profiles = require_eligible_profiles(
            profiles=profiles,
            workload=workload,
        )
        selected_profile = min(
            eligible_profiles,
            key=lambda profile: (
                profile.spot_price_per_hour,
                profile.interruption_probability_per_hour,
                profile.instance_type,
            ),
        )
        cost_estimate = estimate_spot_job_cost(
            profile=selected_profile,
            workload=workload,
            recovery_cost_model=recovery_cost_model,
        )

        return PlacementDecision(
            strategy=self.name,
            market_type=WorkerMarketType.SPOT,
            profile=selected_profile,
            cost_estimate=cost_estimate,
        )


class RiskAwareStrategy:
    name = PlacementStrategyName.RISK_AWARE

    def select(
        self,
        *,
        profiles: Iterable[SpotPoolProfile],
        workload: WorkloadRequirements,
        recovery_cost_model: RecoveryCostModel,
    ) -> PlacementDecision:
        eligible_profiles = require_eligible_profiles(
            profiles=profiles,
            workload=workload,
        )

        selected_profile = min(
            eligible_profiles,
            key=lambda profile: (
                estimate_spot_job_cost(
                    profile=profile,
                    workload=workload,
                    recovery_cost_model=recovery_cost_model,
                ).expected_total_cost,
                profile.interruption_probability_per_hour,
                profile.spot_price_per_hour,
                profile.instance_type,
            ),
        )
        cost_estimate = estimate_spot_job_cost(
            profile=selected_profile,
            workload=workload,
            recovery_cost_model=recovery_cost_model,
        )

        return PlacementDecision(
            strategy=self.name,
            market_type=WorkerMarketType.SPOT,
            profile=selected_profile,
            cost_estimate=cost_estimate,
        )


class OnDemandStrategy:
    name = PlacementStrategyName.ON_DEMAND

    def select(
        self,
        *,
        profiles: Iterable[SpotPoolProfile],
        workload: WorkloadRequirements,
        recovery_cost_model: RecoveryCostModel,
    ) -> PlacementDecision:
        del recovery_cost_model

        eligible_profiles = require_eligible_profiles(
            profiles=profiles,
            workload=workload,
        )
        selected_profile = min(
            eligible_profiles,
            key=lambda profile: (
                estimate_on_demand_job_cost(
                    profile=profile,
                    workload=workload,
                ),
                profile.instance_type,
            ),
        )
        on_demand_cost = estimate_on_demand_job_cost(
            profile=selected_profile,
            workload=workload,
        )

        return PlacementDecision(
            strategy=self.name,
            market_type=WorkerMarketType.ON_DEMAND,
            profile=selected_profile,
            cost_estimate=CostEstimate(
                base_compute_cost=on_demand_cost,
                interruption_probability=0.0,
                expected_recovery_cost=0.0,
                expected_total_cost=on_demand_cost,
            ),
        )


def get_strategy(strategy_name: PlacementStrategyName):
    strategies = {
        PlacementStrategyName.CHEAPEST: CheapestStrategy(),
        PlacementStrategyName.RISK_AWARE: RiskAwareStrategy(),
        PlacementStrategyName.ON_DEMAND: OnDemandStrategy(),
    }
    return strategies[strategy_name]
