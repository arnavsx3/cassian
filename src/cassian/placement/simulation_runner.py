import argparse
from pathlib import Path

from cassian.placement.catalog import get_spot_pool_profiles
from cassian.placement.models import RecoveryCostModel, WorkloadRequirements
from cassian.placement.simulator import (
    SimulationAssumptions,
    SimulationConfig,
    format_comparison_csv,
    format_comparison_json,
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
    parser.add_argument(
        "--output-format",
        choices=["table", "csv", "json"],
        default="table",
    )

    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--output-dir", type=Path)
    output_group.add_argument("--output-file", type=Path)

    return parser


def main() -> None:
    parser = build_parser()
    arguments = parser.parse_args()

    if arguments.output_file is not None and len(arguments.jobs) != 1:
        parser.error("--output-file requires exactly one value in --jobs")

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
        output = _format_output(
            results=results,
            output_format=arguments.output_format,
        )

        output_path = _resolve_output_path(
            output_dir=arguments.output_dir,
            output_file=arguments.output_file,
            job_count=job_count,
            output_format=arguments.output_format,
        )

        if output_path is None:
            print(f"\nSimulation: {job_count:,} jobs, seed={arguments.seed}")
            print(output)
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output, encoding="utf-8")
            print(f"Wrote {output_path}")


def _format_output(*, results, output_format: str) -> str:
    if output_format == "csv":
        return format_comparison_csv(results)

    if output_format == "json":
        return format_comparison_json(results)

    return format_comparison_table(results)


def _resolve_output_path(
    *,
    output_dir: Path | None,
    output_file: Path | None,
    job_count: int,
    output_format: str,
) -> Path | None:
    if output_file is not None:
        return output_file

    if output_dir is None:
        return None

    extension = {
        "table": "txt",
        "csv": "csv",
        "json": "json",
    }[output_format]

    return output_dir / f"simulation_{job_count}.{extension}"


if __name__ == "__main__":
    main()
