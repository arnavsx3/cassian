import time

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from cassian.app import app


@pytest.mark.asyncio
async def test_health() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_job_flows_to_completion() -> None:
    with TestClient(app) as client:
        create_response = client.post(
            "/jobs",
            json={"total_records": 100_000, "chunk_size": 50_000},
        )

        assert create_response.status_code == 201
        job_id = create_response.json()["job_id"]

        final_payload = None
        for _ in range(20):
            job_response = client.get(f"/jobs/{job_id}")
            final_payload = job_response.json()
            if final_payload["status"] == "COMPLETED":
                break
            time.sleep(0.05)

        assert final_payload is not None
        assert final_payload["status"] == "COMPLETED"
        assert final_payload["processed_records"] == 100_000
        assert final_payload["progress_percent"] == 100.0
