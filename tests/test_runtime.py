from cassian.core.config import Settings
from cassian.infra.queueing import InMemoryJobQueue
from cassian.runtime import build_job_queue


def test_build_job_queue_returns_memory_queue() -> None:
    settings = Settings(
        queue_backend="memory",
        checkpoint_backend="filesystem",
        embedded_worker_enabled=False,
    )

    queue = build_job_queue(settings)
    assert isinstance(queue, InMemoryJobQueue)


def test_build_job_queue_requires_sqs_queue_url() -> None:
    settings = Settings(
        queue_backend="sqs",
        checkpoint_backend="filesystem",
        embedded_worker_enabled=False,
    )

    try:
        build_job_queue(settings)
    except ValueError as exc:
        assert "SQS_QUEUE_URL" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing SQS_QUEUE_URL")
