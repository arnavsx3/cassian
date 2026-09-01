import pytest

from cassian.placement.cost_model import (
    estimate_on_demand_job_cost,
    estimate_spot_job_cost,
    interruption_probability_for_runtime,
)
from cassian.placement.models import (
    RecoveryCostModel,
    SpotPoolProfile,
    WorkloadRequirements,
)


def test_interruption_probability_accumulates_over_runtime() -> None:
    probability = interruption_probability_for_runtime(
        interruption_probability_per_hour=0.1,
        runtime_hours=2,
    )

    assert probability == pytest.approx(0.19)


def test_spot_cost_includes_expected_recovery_cost() -> None:
    profile = SpotPoolProfile(
        instance_type="test.large",
        region="test-1",
        vcpus=2,
        memory_gib=4.0,
        spot_price_per_hour=2.0,
        on_demand_price_per_hour=5.0,
        interruption_probability_per_hour=0.1,
    )
    workload = WorkloadRequirements(
        required_vcpus=2,
        required_memory_gib=4.0,
        estimated_runtime_hours=2.0,
    )
    recovery_cost_model = RecoveryCostModel(
        checkpoint_recovery_cost=1.0,
        relaunch_cost=3.0,
    )

    estimate = estimate_spot_job_cost(
        profile=profile,
        workload=workload,
        recovery_cost_model=recovery_cost_model,
    )

    assert estimate.base_compute_cost == pytest.approx(4.0)
    assert estimate.interruption_probability == pytest.approx(0.19)
    assert estimate.expected_recovery_cost == pytest.approx(0.76)
    assert estimate.expected_total_cost == pytest.approx(4.76)


def test_on_demand_cost_has_no_interruption_recovery_component() -> None:
    profile = SpotPoolProfile(
        instance_type="test.large",
        region="test-1",
        vcpus=2,
        memory_gib=4.0,
        spot_price_per_hour=2.0,
        on_demand_price_per_hour=5.0,
        interruption_probability_per_hour=0.1,
    )
    workload = WorkloadRequirements(
        required_vcpus=2,
        required_memory_gib=4.0,
        estimated_runtime_hours=3.0,
    )

    assert estimate_on_demand_job_cost(
        profile=profile,
        workload=workload,
    ) == pytest.approx(15.0)
