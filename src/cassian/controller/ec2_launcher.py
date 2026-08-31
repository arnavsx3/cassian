from dataclasses import dataclass

from cassian.core.aws import build_ec2_client
from cassian.core.config import Settings


@dataclass(slots=True)
class WorkerLaunchResult:
    instance_id: str
    instance_type: str
    market_type: str


class Ec2WorkerLauncher:
    def __init__(self, settings: Settings, client=None) -> None:
        self.settings = settings
        self.client = client or build_ec2_client(settings)

    def launch_spot_worker(self, *, job_id: str) -> WorkerLaunchResult:
        if not self.settings.ec2_worker_ami_id:
            raise ValueError("EC2_WORKER_AMI_ID is required for EC2 worker launches")
        if not self.settings.ec2_worker_instance_type:
            raise ValueError(
                "EC2_WORKER_INSTANCE_TYPE is required for EC2 worker launches"
            )
        if not self.settings.ec2_worker_instance_profile_name:
            raise ValueError(
                "EC2_WORKER_INSTANCE_PROFILE_NAME is required for EC2 worker launches"
            )

        network_interfaces = [
            {
                "DeviceIndex": 0,
                "AssociatePublicIpAddress": True,
            }
        ]

        if self.settings.ec2_worker_subnet_id:
            network_interfaces[0]["SubnetId"] = self.settings.ec2_worker_subnet_id

        if self.settings.ec2_worker_security_group_ids:
            network_interfaces[0]["Groups"] = (
                self.settings.ec2_worker_security_group_ids
            )

        response = self.client.run_instances(
            ImageId=self.settings.ec2_worker_ami_id,
            InstanceType=self.settings.ec2_worker_instance_type,
            MinCount=1,
            MaxCount=1,
            IamInstanceProfile={
                "Name": self.settings.ec2_worker_instance_profile_name,
            },
            InstanceMarketOptions={
                "MarketType": "spot",
                "SpotOptions": {
                    "SpotInstanceType": "one-time",
                    "InstanceInterruptionBehavior": "terminate",
                },
            },
            UserData=self._build_user_data(job_id),
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [
                        {"Key": "Name", "Value": f"cassian-worker-{job_id.lower()}"},
                        {"Key": "CassianJobId", "Value": job_id},
                        {"Key": "CassianManaged", "Value": "true"},
                    ],
                }
            ],
            NetworkInterfaces=network_interfaces,
        )

        instance = response["Instances"][0]
        return WorkerLaunchResult(
            instance_id=instance["InstanceId"],
            instance_type=self.settings.ec2_worker_instance_type,
            market_type="spot",
        )

    def _build_user_data(self, job_id: str) -> str:
        lines = [
            "#!/bin/bash",
            "set -euxo pipefail",
            f"echo CASSIAN_JOB_ID={job_id} >> /etc/environment",
            f"echo AWS_REGION={self.settings.aws_region} >> /etc/environment",
            f"echo CHECKPOINT_BACKEND={self.settings.checkpoint_backend} >> /etc/environment",
            f"echo QUEUE_BACKEND={self.settings.queue_backend} >> /etc/environment",
        ]

        if self.settings.s3_checkpoint_bucket:
            lines.append(
                f"echo S3_CHECKPOINT_BUCKET={self.settings.s3_checkpoint_bucket} >> /etc/environment"
            )
        if self.settings.s3_checkpoint_prefix:
            lines.append(
                f"echo S3_CHECKPOINT_PREFIX={self.settings.s3_checkpoint_prefix} >> /etc/environment"
            )
        if self.settings.sqs_queue_url:
            lines.append(
                f"echo SQS_QUEUE_URL={self.settings.sqs_queue_url} >> /etc/environment"
            )

        lines.extend(
            [
                "source /etc/environment",
                "cd /opt/cassian",
                "uv run cassian-worker",
            ]
        )
        return "\n".join(lines)
