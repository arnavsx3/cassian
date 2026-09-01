import csv
import json
from io import StringIO

import pytest

from cassian.placement.models import (
    PlacementStrategyName,
    RecoveryCostModel,
    SpotPoolProfile,
    WorkerMarketType,
    WorkloadRequirements,
)
from cassian.placement.simulator import (
    SimulationAssumptions,
    SimulationConfig,
    format_comparison_csv,
    format_comparison_json,
    format_comparison_table,
    simulate_comparison,
    simulate_strategy,
)


@pytest.fixture
def profiles() -> tuple[SpotPoolProfile, ...]:
    return (
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
    )


@pytest.fixture
def config(
    profiles: tuple[SpotPoolProfile, ...],
) -> SimulationConfig:
    return SimulationConfig(
        profiles=profiles,
        workload=WorkloadRequirements(
            required_vcpus=2,
            required_memory_gib=4.0,
            estimated_runtime_hours=2.0,
        ),
        recovery_cost_model=RecoveryCostModel(
            checkpoint_recovery_cost=1.0,
            relaunch_cost=4.0,
        ),
        assumptions=SimulationAssumptions(
            checkpoint_interval_hours=0.5,
            recovery_time_hours=0.25,
            max_spot_attempts=3,
        ),
        job_count=100,
        seed=42,
    )


def test_simulation_is_deterministic(config: SimulationConfig) -> None:
    first_run = simulate_comparison(config)
    second_run = simulate_comparison(config)

    assert first_run == second_run


def test_on_demand_completes_all_jobs_without_interruptions(
    config: SimulationConfig,
) -> None:
    result = simulate_strategy(
        config=config,
        strategy_name=PlacementStrategyName.ON_DEMAND,
    )

    assert result.market_type == WorkerMarketType.ON_DEMAND
    assert result.completed_jobs == 100
    assert result.failed_jobs == 0
    assert result.interruption_count == 0
    assert result.completion_rate_percent == 100.0
    assert result.total_recovery_time_hours == 0.0


def test_spot_strategy_reports_interruptions_and_recovery_time(
    config: SimulationConfig,
) -> None:
    result = simulate_strategy(
        config=config,
        strategy_name=PlacementStrategyName.CHEAPEST,
    )

    assert result.market_type == WorkerMarketType.SPOT
    assert result.interruption_count > 0
    assert result.total_recovery_time_hours > 0
    assert result.completed_jobs + result.failed_jobs == result.total_jobs


def test_comparison_table_contains_each_strategy(
    config: SimulationConfig,
) -> None:
    table = format_comparison_table(simulate_comparison(config))

    assert "CHEAPEST" in table
    assert "RISK_AWARE" in table
    assert "ON_DEMAND" in table


def test_csv_output_round_trips_simulation_result(
    config: SimulationConfig,
) -> None:
    results = simulate_comparison(config)
    parsed_rows = list(csv.DictReader(StringIO(format_comparison_csv(results))))

    assert len(parsed_rows) == len(results)
    assert parsed_rows[0]["strategy"] == results[0].strategy.value
    assert int(parsed_rows[0]["total_jobs"]) == results[0].total_jobs
    assert float(parsed_rows[0]["total_cost"]) == pytest.approx(results[0].total_cost)


def test_json_output_round_trips_simulation_result(
    config: SimulationConfig,
) -> None:
    results = simulate_comparison(config)
    parsed_results = json.loads(format_comparison_json(results))

    assert len(parsed_results) == len(results)
    assert parsed_results[0]["strategy"] == results[0].strategy.value
    assert parsed_results[0]["instance_type"] == results[0].instance_type
    assert parsed_results[0]["total_jobs"] == results[0].total_jobs
    assert parsed_results[0]["total_cost"] == pytest.approx(results[0].total_cost)
