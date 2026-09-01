import argparse

from cassian.placement.catalog import get_spot_pool_profiles
from cassian.placement.models import RecoveryCostModel, WorkloadRequirements
from cassian.placement.simulator import (
    SimulationAssumptions,
    SimulationConfig,
    format_comparison_table,
    simulate_comparison,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic Cassian placement simulations."
    )
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument(
        "--jobs",
        type=int,
        nargs="+",
        default=[1_000, 10_000, 100_000],
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--vcpus", type=int, default=2)
    parser.add_argument("--memory-gib", type=float, default=4.0)
    parser.add_argument("--runtime-hours", type=float, default=6.0)
    parser.add_argument("--checkpoint-interval-hours", type=float, default=0.5)
    parser.add_argument("--recovery-time-hours", type=float, default=0.25)
    parser.add_argument("--checkpoint-recovery-cost", type=float, default=2.0)
    parser.add_argument("--relaunch-cost", type=float, default=8.0)
    parser.add_argument("--max-spot-attempts", type=int, default=3)
    return parser


def main() -> None:
    arguments = build_parser().parse_args()
    profiles = tuple(get_spot_pool_profiles(region=arguments.region))

    workload = WorkloadRequirements(
        required_vcpus=arguments.vcpus,
        required_memory_gib=arguments.memory_gib,
        estimated_runtime_hours=arguments.runtime_hours,
    )
    recovery_cost_model = RecoveryCostModel(
        checkpoint_recovery_cost=arguments.checkpoint_recovery_cost,
        relaunch_cost=arguments.relaunch_cost,
    )
    assumptions = SimulationAssumptions(
        checkpoint_interval_hours=arguments.checkpoint_interval_hours,
        recovery_time_hours=arguments.recovery_time_hours,
        max_spot_attempts=arguments.max_spot_attempts,
    )

    for job_count in arguments.jobs:
        config = SimulationConfig(
            profiles=profiles,
            workload=workload,
            recovery_cost_model=recovery_cost_model,
            assumptions=assumptions,
            job_count=job_count,
            seed=arguments.seed,
        )
        results = simulate_comparison(config)

        print(f"\nSimulation: {job_count:,} jobs, seed={arguments.seed}")
        print(format_comparison_table(results))


if __name__ == "__main__":
    main()
