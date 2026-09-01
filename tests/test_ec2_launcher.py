from cassian.controller.ec2_launcher import Ec2WorkerLauncher
from cassian.core.config import Settings
from cassian.placement.models import PlacementStrategyName, WorkerMarketType


class StubEc2Client:
    def __init__(self) -> None:
        self.run_instances_calls: list[dict] = []
        self.terminate_instances_calls: list[dict] = []

    def run_instances(self, **kwargs):
        self.run_instances_calls.append(kwargs)
        return {
            "Instances": [
                {
                    "InstanceId": "i-1234567890abcdef0",
                }
            ]
        }

    def terminate_instances(self, **kwargs) -> None:
        self.terminate_instances_calls.append(kwargs)


def test_ec2_launcher_creates_strategy_selected_spot_worker() -> None:
    client = StubEc2Client()
    settings = Settings(
        aws_region="ap-south-1",
        checkpoint_backend="s3",
        queue_backend="sqs",
        embedded_worker_enabled=False,
        worker_execution_mode="ec2",
        ec2_worker_ami_id="ami-12345678",
        ec2_worker_instance_profile_name="cassian-worker-role",
        ec2_worker_subnet_id="subnet-12345678",
        ec2_worker_security_group_ids=["sg-12345678"],
        s3_checkpoint_bucket="cassian-checkpoints",
        s3_checkpoint_prefix="cassian/checkpoints",
        sqs_queue_url="https://sqs.ap-south-1.amazonaws.com/123/cassian-jobs",
    )

    launcher = Ec2WorkerLauncher(settings=settings, client=client)
    result = launcher.launch_worker(
        job_id="JOB-ABCD1234",
        worker_generation=2,
        instance_type="c6i.large",
        market_type=WorkerMarketType.SPOT,
        placement_strategy=PlacementStrategyName.RISK_AWARE,
    )

    assert result.instance_id == "i-1234567890abcdef0"
    assert result.instance_type == "c6i.large"
    assert result.market_type == "spot"

    request = client.run_instances_calls[0]
    assert request["ImageId"] == "ami-12345678"
    assert request["InstanceType"] == "c6i.large"
    assert request["InstanceMarketOptions"]["MarketType"] == "spot"
    assert request["InstanceInitiatedShutdownBehavior"] == "terminate"
    assert "CASSIAN_WORKER_GENERATION=2" in request["UserData"]
    assert "CASSIAN_PLACEMENT_STRATEGY=RISK_AWARE" in request["UserData"]

    launcher.terminate_worker(instance_id="i-1234567890abcdef0")

    assert client.terminate_instances_calls == [
        {"InstanceIds": ["i-1234567890abcdef0"]}
    ]


def test_ec2_launcher_omits_spot_options_for_on_demand_worker() -> None:
    client = StubEc2Client()
    settings = Settings(
        aws_region="ap-south-1",
        worker_execution_mode="ec2",
        ec2_worker_ami_id="ami-12345678",
        ec2_worker_instance_profile_name="cassian-worker-role",
    )

    launcher = Ec2WorkerLauncher(settings=settings, client=client)
    launcher.launch_worker(
        job_id="JOB-ABCD1234",
        worker_generation=1,
        instance_type="m6i.large",
        market_type=WorkerMarketType.ON_DEMAND,
        placement_strategy=PlacementStrategyName.ON_DEMAND,
    )

    request = client.run_instances_calls[0]

    assert request["InstanceType"] == "m6i.large"
    assert "InstanceMarketOptions" not in request
