from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

async def test_request_id_propagated(client: AsyncClient) -> None:
    response = await client.post("/events", json={"event_type": "test"})
    assert "x-request-id" in response.headers


async def test_request_id_forwarded(client: AsyncClient) -> None:
    response = await client.get("/healthz/live", headers={"X-Request-ID": "my-trace-id"})
    assert response.headers["x-request-id"] == "my-trace-id"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

async def test_liveness(client: AsyncClient) -> None:
    response = await client.get("/healthz/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "uptime_seconds" in data


async def test_readiness(client: AsyncClient) -> None:
    response = await client.get("/healthz/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"
