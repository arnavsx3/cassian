from cassian.placement.models import SpotPoolProfile

SIMULATION_DATASET_VERSION = "2026-09-01-demo-v1"

# Curated, fixed simulation fixtures. These are deliberately not live AWS prices
# or AWS-guaranteed interruption probabilities. They keep simulation results
# deterministic and make the strategy comparison reproducible.
SPOT_POOL_PROFILES: tuple[SpotPoolProfile, ...] = (
    SpotPoolProfile(
        instance_type="c6i.large",
        region="ap-south-1",
        vcpus=2,
        memory_gib=4.0,
        spot_price_per_hour=0.031,
        on_demand_price_per_hour=0.096,
        interruption_probability_per_hour=0.004,
    ),
    SpotPoolProfile(
        instance_type="c6i.xlarge",
        region="ap-south-1",
        vcpus=4,
        memory_gib=8.0,
        spot_price_per_hour=0.061,
        on_demand_price_per_hour=0.192,
        interruption_probability_per_hour=0.008,
    ),
    SpotPoolProfile(
        instance_type="m6i.large",
        region="ap-south-1",
        vcpus=2,
        memory_gib=8.0,
        spot_price_per_hour=0.039,
        on_demand_price_per_hour=0.118,
        interruption_probability_per_hour=0.003,
    ),
    SpotPoolProfile(
        instance_type="m6i.xlarge",
        region="ap-south-1",
        vcpus=4,
        memory_gib=16.0,
        spot_price_per_hour=0.077,
        on_demand_price_per_hour=0.236,
        interruption_probability_per_hour=0.006,
    ),
    SpotPoolProfile(
        instance_type="r6i.large",
        region="ap-south-1",
        vcpus=2,
        memory_gib=16.0,
        spot_price_per_hour=0.051,
        on_demand_price_per_hour=0.151,
        interruption_probability_per_hour=0.002,
    ),
    SpotPoolProfile(
        instance_type="c7i.xlarge",
        region="ap-south-1",
        vcpus=4,
        memory_gib=8.0,
        spot_price_per_hour=0.057,
        on_demand_price_per_hour=0.198,
        interruption_probability_per_hour=0.014,
    ),
)


def get_spot_pool_profiles(*, region: str) -> list[SpotPoolProfile]:
    return [profile for profile in SPOT_POOL_PROFILES if profile.region == region]
