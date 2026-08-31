from cassian.controller.ec2_launcher import Ec2WorkerLauncher, WorkerLaunchResult
from cassian.core.config import Settings


class WorkerDispatcher:
    def __init__(
        self, settings: Settings, ec2_launcher: Ec2WorkerLauncher | None = None
    ) -> None:
        self.settings = settings
        self.ec2_launcher = ec2_launcher or Ec2WorkerLauncher(settings)

    def dispatch(self, *, job_id: str) -> WorkerLaunchResult | None:
        if self.settings.worker_execution_mode == "local":
            return None

        if self.settings.worker_execution_mode == "ec2":
            return self.ec2_launcher.launch_spot_worker(job_id=job_id)

        raise ValueError(
            f"Unsupported WORKER_EXECUTION_MODE: {self.settings.worker_execution_mode}"
        )
