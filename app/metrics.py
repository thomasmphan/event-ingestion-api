from prometheus_client import Counter


events_ingested_total = Counter(
    "events_ingested_total",
    "Total number of individual events ingested via POST /events",
    ["event_type"],
)

events_bulk_ingested_total = Counter(
    "events_bulk_ingested_total",
    "Total number of events ingested via POST /events/bulk",
)

rate_limit_exceeded_total = Counter(
    "rate_limit_exceeded_total",
    "Total number of requests rejected with HTTP 429",
    ["path"],
)
