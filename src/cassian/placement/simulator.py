import csv
import json
from collections.abc import Iterable
from dataclasses import dataclass
from io import StringIO
from random import Random

from cassian.placement.cost_model import interruption_probability_for_runtime
from cassian.placement.models import (
    PlacementStrategyName,
    RecoveryCostModel,
    SpotPoolProfile,
    WorkerMarketType,
    WorkloadRequirements,
)
from cassian.placement.strategies import get_strategy

SIMULATION_RESULT_COLUMNS = (
    "strategy",
    "instance_type",
    "market_type",
    "total_jobs",
    "completed_jobs",
    "failed_jobs",
    "completion_rate_percent",
    "interruption_count",
    "total_cost",
    "average_cost_per_job",
    "total_recovery_time_hours",
    "average_recovery_time_hours",
)


@dataclass(frozen=True, slots=True)
class SimulationAssumptions:
    checkpoint_interval_hours: float = 0.5
    recovery_time_hours: float = 0.25
    max_spot_attempts: int = 3

    def __post_init__(self) -> None:
        if self.checkpoint_interval_hours <= 0:
            raise ValueError("checkpoint_interval_hours must be greater than zero")
        if self.recovery_time_hours < 0:
            raise ValueError("recovery_time_hours cannot be negative")
        if self.max_spot_attempts <= 0:
            raise ValueError("max_spot_attempts must be greater than zero")


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    profiles: tuple[SpotPoolProfile, ...]
    workload: WorkloadRequirements
    recovery_cost_model: RecoveryCostModel
    assumptions: SimulationAssumptions
    job_count: int
    seed: int

    def __post_init__(self) -> None:
        if not self.profiles:
            raise ValueError("profiles cannot be empty")
        if self.job_count <= 0:
            raise ValueError("job_count must be greater than zero")


@dataclass(frozen=True, slots=True)
class SimulationResult:
    strategy: PlacementStrategyName
    instance_type: str
    market_type: WorkerMarketType
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    interruption_count: int
    total_cost: float
    average_cost_per_job: float
    total_recovery_time_hours: float
    average_recovery_time_hours: float

    @property
    def completion_rate_percent(self) -> float:
        return (self.completed_jobs / self.total_jobs) * 100

    def to_dict(self) -> dict[str, str | int | float]:
        return {
            "strategy": self.strategy.value,
            "instance_type": self.instance_type,
            "market_type": self.market_type.value,
            "total_jobs": self.total_jobs,
            "completed_jobs": self.completed_jobs,
            "failed_jobs": self.failed_jobs,
            "completion_rate_percent": self.completion_rate_percent,
            "interruption_count": self.interruption_count,
            "total_cost": self.total_cost,
            "average_cost_per_job": self.average_cost_per_job,
            "total_recovery_time_hours": self.total_recovery_time_hours,
            "average_recovery_time_hours": self.average_recovery_time_hours,
        }


def simulate_comparison(
    config: SimulationConfig,
) -> list[SimulationResult]:
    return [
        simulate_strategy(
            config=config,
            strategy_name=strategy_name,
        )
        for strategy_name in PlacementStrategyName
    ]


def simulate_strategy(
    *,
    config: SimulationConfig,
    strategy_name: PlacementStrategyName,
) -> SimulationResult:
    strategy = get_strategy(strategy_name)
    decision = strategy.select(
        profiles=config.profiles,
        workload=config.workload,
        recovery_cost_model=config.recovery_cost_model,
    )

    if decision.market_type == WorkerMarketType.ON_DEMAND:
        return _simulate_on_demand_jobs(
            config=config,
            strategy_name=strategy_name,
            instance_type=decision.profile.instance_type,
            hourly_price=decision.profile.on_demand_price_per_hour,
        )

    return _simulate_spot_jobs(
        config=config,
        strategy_name=strategy_name,
        profile=decision.profile,
    )


def format_comparison_table(results: Iterable[SimulationResult]) -> str:
    rows = [
        (
            result.strategy.value,
            result.instance_type,
            result.market_type.value,
            str(result.total_jobs),
            f"{result.completion_rate_percent:.2f}%",
            str(result.interruption_count),
            f"${result.total_cost:.2f}",
            f"${result.average_cost_per_job:.4f}",
            f"{result.average_recovery_time_hours:.3f}h",
        )
        for result in results
    ]
    headers = (
        "Strategy",
        "Instance",
        "Market",
        "Jobs",
        "Completion",
        "Interruptions",
        "Total Cost",
        "Avg Job Cost",
        "Avg Recovery",
    )
    widths = [
        max(len(header), *(len(row[index]) for row in rows))
        for index, header in enumerate(headers)
    ]

    def format_row(row: tuple[str, ...]) -> str:
        return " | ".join(value.ljust(widths[index]) for index, value in enumerate(row))

    separator = "-+-".join("-" * width for width in widths)
    return "\n".join(
        [
            format_row(headers),
            separator,
            *(format_row(row) for row in rows),
        ]
    )


def format_comparison_csv(results: Iterable[SimulationResult]) -> str:
    output = StringIO(newline="")
    fieldnames: list[str] = list(SIMULATION_RESULT_COLUMNS)
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
    )
    writer.writeheader()

    for result in results:
        writer.writerow(result.to_dict())

    return output.getvalue()


def format_comparison_json(results: Iterable[SimulationResult]) -> str:
    return json.dumps(
        [result.to_dict() for result in results],
        indent=2,
        sort_keys=True,
    )


def _simulate_on_demand_jobs(
    *,
    config: SimulationConfig,
    strategy_name: PlacementStrategyName,
    instance_type: str,
    hourly_price: float,
) -> SimulationResult:
    job_cost = hourly_price * config.workload.estimated_runtime_hours
    total_cost = job_cost * config.job_count

    return SimulationResult(
        strategy=strategy_name,
        instance_type=instance_type,
        market_type=WorkerMarketType.ON_DEMAND,
        total_jobs=config.job_count,
        completed_jobs=config.job_count,
        failed_jobs=0,
        interruption_count=0,
        total_cost=total_cost,
        average_cost_per_job=job_cost,
        total_recovery_time_hours=0.0,
        average_recovery_time_hours=0.0,
    )


def _simulate_spot_jobs(
    *,
    config: SimulationConfig,
    strategy_name: PlacementStrategyName,
    profile: SpotPoolProfile,
) -> SimulationResult:
    random = Random(config.seed)
    completed_jobs = 0
    interruption_count = 0
    total_cost = 0.0
    total_recovery_time_hours = 0.0

    for _ in range(config.job_count):
        (
            completed,
            job_interruptions,
            job_cost,
            job_recovery_time_hours,
        ) = _simulate_spot_job(
            profile=profile,
            config=config,
            random=random,
        )

        if completed:
            completed_jobs += 1

        interruption_count += job_interruptions
        total_cost += job_cost
        total_recovery_time_hours += job_recovery_time_hours

    failed_jobs = config.job_count - completed_jobs

    return SimulationResult(
        strategy=strategy_name,
        instance_type=profile.instance_type,
        market_type=WorkerMarketType.SPOT,
        total_jobs=config.job_count,
        completed_jobs=completed_jobs,
        failed_jobs=failed_jobs,
        interruption_count=interruption_count,
        total_cost=total_cost,
        average_cost_per_job=total_cost / config.job_count,
        total_recovery_time_hours=total_recovery_time_hours,
        average_recovery_time_hours=(total_recovery_time_hours / config.job_count),
    )


def _simulate_spot_job(
    *,
    profile: SpotPoolProfile,
    config: SimulationConfig,
    random: Random,
) -> tuple[bool, int, float, float]:
    remaining_runtime_hours = config.workload.estimated_runtime_hours
    interruption_count = 0
    attempted_launches = 1
    job_cost = 0.0
    recovery_time_hours = 0.0

    while remaining_runtime_hours > 0:
        checkpoint_segment_hours = min(
            config.assumptions.checkpoint_interval_hours,
            remaining_runtime_hours,
        )
        interruption_probability = interruption_probability_for_runtime(
            interruption_probability_per_hour=(
                profile.interruption_probability_per_hour
            ),
            runtime_hours=checkpoint_segment_hours,
        )

        if random.random() < interruption_probability:
            interruption_count += 1
            attempted_runtime_hours = checkpoint_segment_hours * random.random()
            job_cost += profile.spot_price_per_hour * attempted_runtime_hours

            if attempted_launches >= config.assumptions.max_spot_attempts:
                return (
                    False,
                    interruption_count,
                    job_cost,
                    recovery_time_hours,
                )

            attempted_launches += 1
            job_cost += config.recovery_cost_model.total_recovery_cost
            recovery_time_hours += config.assumptions.recovery_time_hours
            continue

        job_cost += profile.spot_price_per_hour * checkpoint_segment_hours
        remaining_runtime_hours -= checkpoint_segment_hours

    return True, interruption_count, job_cost, recovery_time_hours
