from httpx import AsyncClient


# ---------------------------------------------------------------------------
# POST /events
# ---------------------------------------------------------------------------

async def test_create_event(client: AsyncClient) -> None:
    response = await client.post("/events", json={
        "event_type": "page_view",
        "source": "web",
        "payload": {"url": "/home"},
        "timestamp": "2024-01-01T00:00:00Z",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["event_type"] == "page_view"
    assert data["source"] == "web"
    assert data["payload"] == {"url": "/home"}
    assert "id" in data
    assert "created_at" in data


async def test_create_event_minimal(client: AsyncClient) -> None:
    response = await client.post("/events", json={"event_type": "click"})
    assert response.status_code == 201
    data = response.json()
    assert data["event_type"] == "click"
    assert data["source"] is None
    assert data["payload"] == {}
    assert data["timestamp"] is not None


async def test_create_event_missing_required(client: AsyncClient) -> None:
    response = await client.post("/events", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /events/{id}
# ---------------------------------------------------------------------------

async def test_get_event(client: AsyncClient) -> None:
    create = await client.post("/events", json={"event_type": "login"})
    event_id = create.json()["id"]

    response = await client.get(f"/events/{event_id}")
    assert response.status_code == 200
    assert response.json()["id"] == event_id


async def test_get_event_not_found(client: AsyncClient) -> None:
    response = await client.get("/events/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /events (list + filters + cursor)
# ---------------------------------------------------------------------------

async def test_list_events_filter_by_type(client: AsyncClient) -> None:
    await client.post("/events", json={"event_type": "click"})
    await client.post("/events", json={"event_type": "purchase"})

    response = await client.get("/events", params={"event_type": "click"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["event_type"] == "click"


async def test_list_events_limit_too_large(client: AsyncClient) -> None:
    response = await client.get("/events", params={"limit": 1001})
    assert response.status_code == 422


async def test_list_events_cursor_pagination(client: AsyncClient) -> None:
    # Create 3 events — timestamps will differ by insertion order
    for i in range(3):
        await client.post("/events", json={
            "event_type": "scroll",
            "payload": {"page": i},
        })

    # Page 1: limit=2, default sort=desc
    page1 = await client.get("/events", params={
        "event_type": "scroll",
        "limit": 2
    })
    assert page1.status_code == 200
    body1 = page1.json()
    assert len(body1["items"]) == 2
    assert body1["total"] == 3
    assert body1["next_cursor"] is not None

    # Page 2: use the cursor
    page2 = await client.get("/events", params={
        "event_type": "scroll",
        "limit": 2,
        "cursor": body1["next_cursor"],
    })
    assert page2.status_code == 200
    body2 = page2.json()
    assert len(body2["items"]) == 1
    assert body2["next_cursor"] is None

    # No overlap between pages
    ids1 = {item["id"] for item in body1["items"]}
    ids2 = {item["id"] for item in body2["items"]}
    assert ids1.isdisjoint(ids2)


async def test_list_events_cursor_ascending(client: AsyncClient) -> None:
    for i in range(3):
        await client.post("/events", json={
            "event_type": "asc_test",
            "payload": {"seq": i},
        })

    page1 = await client.get("/events", params={
        "event_type": "asc_test",
        "limit": 2,
        "sort": "asc",
    })
    body1 = page1.json()
    assert len(body1["items"]) == 2
    assert body1["next_cursor"] is not None
    # Ascending: first item should have an earlier timestamp than the last
    assert body1["items"][0]["timestamp"] <= body1["items"][1]["timestamp"]

    page2 = await client.get("/events", params={
        "event_type": "asc_test",
        "limit": 2,
        "sort": "asc",
        "cursor": body1["next_cursor"],
    })
    body2 = page2.json()
    assert len(body2["items"]) == 1
    assert body2["next_cursor"] is None


async def test_cursor_direction_mismatch(client: AsyncClient) -> None:
    await client.post("/events", json={"event_type": "mismatch_test"})
    await client.post("/events", json={"event_type": "mismatch_test"})

    # Get a cursor from a desc-sorted response
    page1 = await client.get("/events", params={
        "event_type": "mismatch_test",
        "limit": 1,
        "sort": "desc",
    })
    cursor = page1.json()["next_cursor"]
    assert cursor is not None

    # Use that desc cursor with sort=asc — should be rejected
    response = await client.get("/events", params={
        "event_type": "mismatch_test",
        "limit": 1,
        "sort": "asc",
        "cursor": cursor,
    })
    assert response.status_code == 422
    assert "direction" in response.json()["detail"].lower()


async def test_cursor_invalid(client: AsyncClient) -> None:
    response = await client.get("/events", params={"cursor": "not-a-valid-cursor"})
    assert response.status_code == 422


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
