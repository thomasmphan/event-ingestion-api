import pytest

from app import config
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def low_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.settings, "ingest_rate_limit", "3/minute")
    monkeypatch.setattr(config.settings, "bulk_rate_limit", "2/minute")


async def test_ingest_rate_limit(client: AsyncClient) -> None:
    for _ in range(3):
        r = await client.post("/events", json={"event_type": "rl_test"})
        assert r.status_code == 201

    r = await client.post("/events", json={"event_type": "rl_test"})
    assert r.status_code == 429
    assert "retry-after" in r.headers


async def test_bulk_rate_limit(client: AsyncClient) -> None:
    payload = {"events": [{"event_type": "rl_bulk"}]}

    for _ in range(2):
        r = await client.post("/events/bulk", json=payload)
        assert r.status_code == 201

    r = await client.post("/events/bulk", json=payload)
    assert r.status_code == 429
    assert "retry-after" in r.headers
