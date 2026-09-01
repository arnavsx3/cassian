from cassian.placement.models import (
    CostEstimate,
    RecoveryCostModel,
    SpotPoolProfile,
    WorkloadRequirements,
)


def interruption_probability_for_runtime(
    *,
    interruption_probability_per_hour: float,
    runtime_hours: float,
) -> float:
    if not 0 <= interruption_probability_per_hour <= 1:
        raise ValueError(
            "interruption_probability_per_hour must be between zero and one"
        )
    if runtime_hours < 0:
        raise ValueError("runtime_hours cannot be negative")

    return 1 - ((1 - interruption_probability_per_hour) ** runtime_hours)


def estimate_spot_job_cost(
    *,
    profile: SpotPoolProfile,
    workload: WorkloadRequirements,
    recovery_cost_model: RecoveryCostModel,
) -> CostEstimate:
    base_compute_cost = profile.spot_price_per_hour * workload.estimated_runtime_hours
    interruption_probability = interruption_probability_for_runtime(
        interruption_probability_per_hour=profile.interruption_probability_per_hour,
        runtime_hours=workload.estimated_runtime_hours,
    )
    expected_recovery_cost = (
        interruption_probability * recovery_cost_model.total_recovery_cost
    )
    expected_total_cost = base_compute_cost + expected_recovery_cost

    return CostEstimate(
        base_compute_cost=base_compute_cost,
        interruption_probability=interruption_probability,
        expected_recovery_cost=expected_recovery_cost,
        expected_total_cost=expected_total_cost,
    )


def estimate_on_demand_job_cost(
    *,
    profile: SpotPoolProfile,
    workload: WorkloadRequirements,
) -> float:
    return profile.on_demand_price_per_hour * workload.estimated_runtime_hours
