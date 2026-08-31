import boto3

from cassian.core.config import Settings


def build_s3_client(settings: Settings):
    if not settings.aws_region:
        raise ValueError("AWS_REGION is required for S3 operations")
    return boto3.client("s3", region_name=settings.aws_region)


def build_sqs_client(settings: Settings):
    if not settings.aws_region:
        raise ValueError("AWS_REGION is required for SQS operations")
    return boto3.client("sqs", region_name=settings.aws_region)


def build_ec2_client(settings: Settings):
    if not settings.aws_region:
        raise ValueError("AWS_REGION is required for EC2 operations")
    return boto3.client("ec2", region_name=settings.aws_region)
