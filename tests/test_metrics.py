import pytest

from app import config
from app.metrics import events_bulk_ingested_total, events_ingested_total, rate_limit_exceeded_total
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# /metrics endpoint
# ---------------------------------------------------------------------------

async def test_metrics_endpoint_returns_200(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


async def test_metrics_endpoint_contains_http_requests_total(client: AsyncClient) -> None:
    await client.post("/events", json={"event_type": "metrics_probe"})
    response = await client.get("/metrics")
    assert "http_requests_total" in response.text


# ---------------------------------------------------------------------------
# events_ingested_total
# ---------------------------------------------------------------------------

async def test_events_ingested_total_increments(client: AsyncClient) -> None:
    before = events_ingested_total.labels(event_type="counter_test")._value.get()

    await client.post("/events", json={"event_type": "counter_test"})
    await client.post("/events", json={"event_type": "counter_test"})

    after = events_ingested_total.labels(event_type="counter_test")._value.get()
    assert after - before == 2


async def test_events_ingested_total_per_event_type(client: AsyncClient) -> None:
    before_a = events_ingested_total.labels(event_type="type_a")._value.get()
    before_b = events_ingested_total.labels(event_type="type_b")._value.get()

    await client.post("/events", json={"event_type": "type_a"})
    await client.post("/events", json={"event_type": "type_b"})
    await client.post("/events", json={"event_type": "type_a"})

    after_a = events_ingested_total.labels(event_type="type_a")._value.get()
    after_b = events_ingested_total.labels(event_type="type_b")._value.get()
    assert after_a - before_a == 2
    assert after_b - before_b == 1


async def test_events_ingested_not_incremented_on_validation_error(client: AsyncClient) -> None:
    before = sum(child._value.get() for child in events_ingested_total._metrics.values())

    await client.post("/events", json={})  # missing event_type → 422

    after = sum(child._value.get() for child in events_ingested_total._metrics.values())
    assert after == before


# ---------------------------------------------------------------------------
# events_bulk_ingested_total
# ---------------------------------------------------------------------------

async def test_events_bulk_ingested_total_increments_by_batch_size(client: AsyncClient) -> None:
    before = events_bulk_ingested_total._value.get()

    await client.post("/events/bulk", json={
        "events": [
            {"event_type": "bulk_a"},
            {"event_type": "bulk_b"},
            {"event_type": "bulk_c"},
        ]
    })

    after = events_bulk_ingested_total._value.get()
    assert after - before == 3


async def test_events_bulk_ingested_total_accumulates(client: AsyncClient) -> None:
    before = events_bulk_ingested_total._value.get()

    await client.post("/events/bulk", json={"events": [{"event_type": "bulk_acc_1"}]})
    await client.post("/events/bulk", json={"events": [{"event_type": "bulk_acc_2"}, {"event_type": "bulk_acc_3"}]})

    after = events_bulk_ingested_total._value.get()
    assert after - before == 3


# ---------------------------------------------------------------------------
# rate_limit_exceeded_total
# ---------------------------------------------------------------------------

@pytest.fixture()
def low_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.settings, "ingest_rate_limit", "2/minute")


@pytest.mark.usefixtures("low_rate_limits")
async def test_rate_limit_exceeded_total_increments(client: AsyncClient) -> None:
    before = rate_limit_exceeded_total.labels(path="/events")._value.get()

    await client.post("/events", json={"event_type": "rl_metric"})
    await client.post("/events", json={"event_type": "rl_metric"})
    r = await client.post("/events", json={"event_type": "rl_metric"})
    assert r.status_code == 429

    after = rate_limit_exceeded_total.labels(path="/events")._value.get()
    assert after - before == 1


@pytest.mark.usefixtures("low_rate_limits")
async def test_rate_limit_exceeded_total_not_incremented_on_success(client: AsyncClient) -> None:
    before = rate_limit_exceeded_total.labels(path="/events")._value.get()

    r = await client.post("/events", json={"event_type": "rl_ok"})
    assert r.status_code == 201

    after = rate_limit_exceeded_total.labels(path="/events")._value.get()
    assert after - before == 0
