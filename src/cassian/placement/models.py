from dataclasses import dataclass
from enum import Enum


class PlacementStrategyName(str, Enum):
    CHEAPEST = "CHEAPEST"
    RISK_AWARE = "RISK_AWARE"
    ON_DEMAND = "ON_DEMAND"


class WorkerMarketType(str, Enum):
    SPOT = "spot"
    ON_DEMAND = "on-demand"


@dataclass(frozen=True, slots=True)
class WorkloadRequirements:
    required_vcpus: int
    required_memory_gib: float
    estimated_runtime_hours: float

    def __post_init__(self) -> None:
        if self.required_vcpus <= 0:
            raise ValueError("required_vcpus must be greater than zero")
        if self.required_memory_gib <= 0:
            raise ValueError("required_memory_gib must be greater than zero")
        if self.estimated_runtime_hours <= 0:
            raise ValueError("estimated_runtime_hours must be greater than zero")


@dataclass(frozen=True, slots=True)
class SpotPoolProfile:
    instance_type: str
    region: str
    vcpus: int
    memory_gib: float
    spot_price_per_hour: float
    on_demand_price_per_hour: float
    interruption_probability_per_hour: float

    def __post_init__(self) -> None:
        if self.vcpus <= 0:
            raise ValueError("vcpus must be greater than zero")
        if self.memory_gib <= 0:
            raise ValueError("memory_gib must be greater than zero")
        if self.spot_price_per_hour <= 0:
            raise ValueError("spot_price_per_hour must be greater than zero")
        if self.on_demand_price_per_hour <= 0:
            raise ValueError("on_demand_price_per_hour must be greater than zero")
        if not 0 <= self.interruption_probability_per_hour <= 1:
            raise ValueError(
                "interruption_probability_per_hour must be between zero and one"
            )


@dataclass(frozen=True, slots=True)
class RecoveryCostModel:
    checkpoint_recovery_cost: float
    relaunch_cost: float

    def __post_init__(self) -> None:
        if self.checkpoint_recovery_cost < 0:
            raise ValueError("checkpoint_recovery_cost cannot be negative")
        if self.relaunch_cost < 0:
            raise ValueError("relaunch_cost cannot be negative")

    @property
    def total_recovery_cost(self) -> float:
        return self.checkpoint_recovery_cost + self.relaunch_cost


@dataclass(frozen=True, slots=True)
class CostEstimate:
    base_compute_cost: float
    interruption_probability: float
    expected_recovery_cost: float
    expected_total_cost: float


@dataclass(frozen=True, slots=True)
class PlacementDecision:
    strategy: PlacementStrategyName
    market_type: WorkerMarketType
    profile: SpotPoolProfile
    cost_estimate: CostEstimate
