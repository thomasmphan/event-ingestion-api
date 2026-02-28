import time

from app.database import get_db
from app.schemas import LivenessResponse, ReadinessResponse
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(prefix="/healthz", tags=["health"])

START_TIME = time.time()


@router.get("/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok", uptime_seconds=int(time.time() - START_TIME))


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(db: AsyncSession = Depends(get_db)) -> ReadinessResponse | JSONResponse:
    try:
        await db.execute(text("SELECT 1"))
        return ReadinessResponse(status="ok", db="connected")
    except Exception:
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "disconnected"})
