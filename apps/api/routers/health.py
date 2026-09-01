"""Health and readiness endpoints."""

from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness():
    """Liveness probe — is the process running?"""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    """Readiness probe — can we serve traffic?"""
    checks = {}

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # Redis check (placeholder — will connect when Redis client is configured)
    checks["redis"] = "not_configured"

    # MinIO check (placeholder)
    checks["minio"] = "not_configured"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics endpoint (placeholder)."""
    return {"status": "metrics_placeholder", "note": "Prometheus metrics will be added in Phase 8"}
