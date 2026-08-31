from typing import Protocol

from cassian.controller.ec2_launcher import Ec2WorkerLauncher, WorkerLaunchResult
from cassian.core.config import Settings


class WorkerDispatchPort(Protocol):
    def dispatch(self, *, job_id: str) -> WorkerLaunchResult | None: ...


class WorkerDispatcher:
    def __init__(
        self,
        settings: Settings,
        ec2_launcher: Ec2WorkerLauncher | None = None,
    ) -> None:
        self.settings = settings
        self.ec2_launcher = ec2_launcher

    def dispatch(self, *, job_id: str) -> WorkerLaunchResult | None:
        if self.settings.worker_execution_mode == "local":
            return None

        if self.settings.worker_execution_mode == "ec2":
            if self.ec2_launcher is None:
                raise ValueError("EC2 launcher is not configured")
            return self.ec2_launcher.launch_spot_worker(job_id=job_id)

        raise ValueError(
            f"Unsupported WORKER_EXECUTION_MODE: {self.settings.worker_execution_mode}"
        )
