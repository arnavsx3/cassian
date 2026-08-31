from cassian.controller.ec2_launcher import Ec2WorkerLauncher
from cassian.core.config import Settings


class StubEc2Client:
    def __init__(self) -> None:
        self.run_instances_calls: list[dict] = []

    def run_instances(self, **kwargs):
        self.run_instances_calls.append(kwargs)
        return {
            "Instances": [
                {
                    "InstanceId": "i-1234567890abcdef0",
                }
            ]
        }


def test_ec2_launcher_creates_spot_instance_request() -> None:
    client = StubEc2Client()
    settings = Settings(
        aws_region="ap-south-1",
        checkpoint_backend="s3",
        queue_backend="sqs",
        embedded_worker_enabled=False,
        worker_execution_mode="ec2",
        ec2_worker_ami_id="ami-12345678",
        ec2_worker_instance_type="t3.micro",
        ec2_worker_instance_profile_name="cassian-worker-role",
        ec2_worker_subnet_id="subnet-12345678",
        ec2_worker_security_group_ids=["sg-12345678"],
        s3_checkpoint_bucket="cassian-checkpoints",
        s3_checkpoint_prefix="cassian/checkpoints",
        sqs_queue_url="https://sqs.ap-south-1.amazonaws.com/123/cassian-jobs",
    )

    launcher = Ec2WorkerLauncher(settings=settings, client=client)
    result = launcher.launch_spot_worker(job_id="JOB-ABCD1234")

    assert result.instance_id == "i-1234567890abcdef0"
    assert result.market_type == "spot"
    assert len(client.run_instances_calls) == 1

    request = client.run_instances_calls[0]
    assert request["ImageId"] == "ami-12345678"
    assert request["InstanceType"] == "t3.micro"
    assert request["InstanceMarketOptions"]["MarketType"] == "spot"
