import asyncio
import base64
import json
import structlog

from app.config import settings
from app.database import get_db, get_session_factory
from app.limiter import limiter
from app.models import Event
from app.schemas import EventBulkCreate, EventBulkResponse, EventCreate, EventListResponse, EventResponse
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, insert, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from uuid import UUID


logger = structlog.get_logger()

router = APIRouter(prefix="/events", tags=["events"])


def encode_cursor(timestamp: datetime, event_id: UUID, direction: str) -> str:
    payload = {"ts": timestamp.isoformat(), "id": str(event_id), "dir": direction}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID, str]:
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    return datetime.fromisoformat(payload["ts"]), UUID(payload["id"]), payload["dir"]


@router.post("", response_model=EventResponse, status_code=201)
@limiter.limit(lambda: settings.ingest_rate_limit)
async def create_event(request: Request, event: EventCreate, db: AsyncSession = Depends(get_db)) -> Event:
    db_event = Event(
        event_type=event.event_type,
        source=event.source,
        payload=event.payload,
        timestamp=event.timestamp,
    )
    db.add(db_event)
    await db.commit()
    await db.refresh(db_event)
    logger.info("event_created", event_id=str(db_event.id), event_type=db_event.event_type)
    return db_event


@router.post("/bulk", response_model=EventBulkResponse, status_code=201)
@limiter.limit(lambda: settings.bulk_rate_limit)
async def create_events_bulk(request: Request, body: EventBulkCreate, db: AsyncSession = Depends(get_db)) -> EventBulkResponse:
    rows = [
        {
            "event_type": e.event_type,
            "source": e.source,
            "payload": e.payload,
            "timestamp": e.timestamp,
        }
        for e in body.events
    ]
    stmt = insert(Event).values(rows).returning(Event)
    result = await db.execute(stmt)
    events = list(result.scalars().all())
    await db.commit()
    logger.info("events_bulk_created", count=len(events))
    return EventBulkResponse(created=len(events), items=events)


@router.get("", response_model=EventListResponse)
@limiter.limit(lambda: settings.list_rate_limit)
async def list_events(
    request: Request,
    event_type: str | None = Query(None),
    source: str | None = Query(None),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    sort: str = Query("desc", pattern="^(asc|desc)$"),
    cursor: str | None = Query(None),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> EventListResponse:

    # Build both queries with filters applied
    query = select(Event)
    count_query = select(func.count()).select_from(Event)

    if event_type:
        query = query.where(Event.event_type == event_type)
        count_query = count_query.where(Event.event_type == event_type)
    if source:
        query = query.where(Event.source == source)
        count_query = count_query.where(Event.source == source)
    if start_time:
        query = query.where(Event.timestamp >= start_time)
        count_query = count_query.where(Event.timestamp >= start_time)
    if end_time:
        query = query.where(Event.timestamp <= end_time)
        count_query = count_query.where(Event.timestamp <= end_time)

    if cursor:
        try:
            cursor_ts, cursor_id, cursor_dir = decode_cursor(cursor)
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid cursor")
        
        if cursor_dir != sort:
            raise HTTPException(status_code=422, detail="Cursor sort direction does not match requested sort")

        if sort == "desc":
            query = query.where(
                or_(
                    Event.timestamp < cursor_ts,
                    and_(Event.timestamp == cursor_ts, Event.id < cursor_id),
                )
            )
        else:
            query = query.where(
                or_(
                    Event.timestamp > cursor_ts,
                    and_(Event.timestamp == cursor_ts, Event.id > cursor_id),
                )
            )

    order = (
        (Event.timestamp.desc(), Event.id.desc())
        if sort == "desc"
        else (Event.timestamp.asc(), Event.id.asc())
    )

    async with session_factory() as count_session, \
               session_factory() as data_session:
        total_result, events_result = await asyncio.gather(
            count_session.execute(count_query),
            data_session.execute(query.order_by(*order).limit(limit)),
        )

    total = total_result.scalar()
    events = list(events_result.scalars().all())

    next_cursor = None
    if len(events) == limit:
        last = events[-1]
        next_cursor = encode_cursor(last.timestamp, last.id, sort)

    return EventListResponse(items=events, total=total, limit=limit, next_cursor=next_cursor)


@router.get("/{event_id}", response_model=EventResponse)
@limiter.limit(lambda: settings.get_rate_limit)
async def get_event(request: Request, event_id: UUID, db: AsyncSession = Depends(get_db)) -> Event:
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return event
