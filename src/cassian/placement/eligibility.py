from collections.abc import Iterable

from cassian.placement.models import SpotPoolProfile, WorkloadRequirements


class NoEligibleSpotPoolsError(ValueError):
    """Raised when no candidate instance type can run the workload."""


def filter_eligible_profiles(
    *,
    profiles: Iterable[SpotPoolProfile],
    workload: WorkloadRequirements,
) -> list[SpotPoolProfile]:
    return [
        profile
        for profile in profiles
        if profile.vcpus >= workload.required_vcpus
        and profile.memory_gib >= workload.required_memory_gib
    ]


def require_eligible_profiles(
    *,
    profiles: Iterable[SpotPoolProfile],
    workload: WorkloadRequirements,
) -> list[SpotPoolProfile]:
    eligible_profiles = filter_eligible_profiles(
        profiles=profiles,
        workload=workload,
    )

    if not eligible_profiles:
        raise NoEligibleSpotPoolsError(
            "No candidate Spot pool satisfies the workload requirements"
        )

    return eligible_profiles
