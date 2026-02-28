import asyncio
import httpx

EVENTS = [
    {"event_type": "page_view", "source": "web",    "payload": {"url": "/home"}},
    {"event_type": "page_view", "source": "mobile", "payload": {"url": "/pricing"}},
    {"event_type": "click",     "source": "web",    "payload": {"element": "buy_button"}},
    {"event_type": "purchase",  "source": "web",    "payload": {"amount": 99.99, "item": "Pro Plan"}},
    {"event_type": "page_view", "source": "web",    "payload": {"url": "/docs"}},
    {"event_type": "click",     "source": "mobile", "payload": {"element": "signup_cta"}},
    {"event_type": "signup",    "source": "mobile", "payload": {"plan": "free"}},
    {"event_type": "page_view", "source": "web",    "payload": {"url": "/about"}},
    {"event_type": "click",     "source": "web",    "payload": {"element": "nav_pricing"}},
    {"event_type": "purchase",  "source": "mobile", "payload": {"amount": 49.99, "item": "Starter Plan"}},
]

async def seed() -> None:
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        for event in EVENTS:
            r = await client.post("/events", json=event)
            data = r.json()
            print(f"[{r.status_code}] {data['event_type']:12} | {data['source']:8} | {data['id']}")

asyncio.run(seed())
