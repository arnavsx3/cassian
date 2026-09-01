import pytest

from cassian.placement.eligibility import (
    NoEligibleSpotPoolsError,
    filter_eligible_profiles,
)
from cassian.placement.models import (
    PlacementStrategyName,
    RecoveryCostModel,
    SpotPoolProfile,
    WorkerMarketType,
    WorkloadRequirements,
)
from cassian.placement.strategies import (
    CheapestStrategy,
    OnDemandStrategy,
    RiskAwareStrategy,
)


@pytest.fixture
def workload() -> WorkloadRequirements:
    return WorkloadRequirements(
        required_vcpus=2,
        required_memory_gib=4.0,
        estimated_runtime_hours=1.0,
    )


@pytest.fixture
def recovery_cost_model() -> RecoveryCostModel:
    return RecoveryCostModel(
        checkpoint_recovery_cost=1.0,
        relaunch_cost=4.0,
    )


@pytest.fixture
def profiles() -> list[SpotPoolProfile]:
    return [
        SpotPoolProfile(
            instance_type="cheap-risky",
            region="test-1",
            vcpus=2,
            memory_gib=4.0,
            spot_price_per_hour=1.0,
            on_demand_price_per_hour=4.0,
            interruption_probability_per_hour=0.40,
        ),
        SpotPoolProfile(
            instance_type="stable-spot",
            region="test-1",
            vcpus=2,
            memory_gib=8.0,
            spot_price_per_hour=1.5,
            on_demand_price_per_hour=3.0,
            interruption_probability_per_hour=0.02,
        ),
        SpotPoolProfile(
            instance_type="too-small",
            region="test-1",
            vcpus=1,
            memory_gib=2.0,
            spot_price_per_hour=0.1,
            on_demand_price_per_hour=0.2,
            interruption_probability_per_hour=0.01,
        ),
    ]


def test_eligibility_filter_removes_profiles_without_required_capacity(
    profiles: list[SpotPoolProfile],
    workload: WorkloadRequirements,
) -> None:
    eligible = filter_eligible_profiles(
        profiles=profiles,
        workload=workload,
    )

    assert [profile.instance_type for profile in eligible] == [
        "cheap-risky",
        "stable-spot",
    ]


def test_cheapest_strategy_selects_lowest_spot_price(
    profiles: list[SpotPoolProfile],
    workload: WorkloadRequirements,
    recovery_cost_model: RecoveryCostModel,
) -> None:
    decision = CheapestStrategy().select(
        profiles=profiles,
        workload=workload,
        recovery_cost_model=recovery_cost_model,
    )

    assert decision.strategy == PlacementStrategyName.CHEAPEST
    assert decision.market_type == WorkerMarketType.SPOT
    assert decision.profile.instance_type == "cheap-risky"


def test_risk_aware_strategy_selects_lowest_expected_total_cost(
    profiles: list[SpotPoolProfile],
    workload: WorkloadRequirements,
    recovery_cost_model: RecoveryCostModel,
) -> None:
    decision = RiskAwareStrategy().select(
        profiles=profiles,
        workload=workload,
        recovery_cost_model=recovery_cost_model,
    )

    assert decision.strategy == PlacementStrategyName.RISK_AWARE
    assert decision.market_type == WorkerMarketType.SPOT
    assert decision.profile.instance_type == "stable-spot"


def test_on_demand_strategy_selects_lowest_eligible_on_demand_cost(
    profiles: list[SpotPoolProfile],
    workload: WorkloadRequirements,
    recovery_cost_model: RecoveryCostModel,
) -> None:
    decision = OnDemandStrategy().select(
        profiles=profiles,
        workload=workload,
        recovery_cost_model=recovery_cost_model,
    )

    assert decision.strategy == PlacementStrategyName.ON_DEMAND
    assert decision.market_type == WorkerMarketType.ON_DEMAND
    assert decision.profile.instance_type == "stable-spot"
    assert decision.cost_estimate.interruption_probability == 0.0


def test_strategy_rejects_when_no_profile_is_eligible(
    profiles: list[SpotPoolProfile],
    recovery_cost_model: RecoveryCostModel,
) -> None:
    oversized_workload = WorkloadRequirements(
        required_vcpus=16,
        required_memory_gib=64.0,
        estimated_runtime_hours=1.0,
    )

    with pytest.raises(NoEligibleSpotPoolsError):
        CheapestStrategy().select(
            profiles=profiles,
            workload=oversized_workload,
            recovery_cost_model=recovery_cost_model,
        )
