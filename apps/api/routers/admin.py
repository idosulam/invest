"""Admin endpoints — PRD Section 9.

Data source configuration, job management, quality monitoring,
model versions, and audit search.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import get_current_user, require_admin
from apps.api.database import get_db
from packages.domain.entities.models import (
    JobRun, DataIssue, Instrument, MarketBar, User,
)
from packages.data.providers.yahoo_finance import YahooFinanceProvider
from packages.data.ingestion.pipeline import IngestionPipeline
from packages.domain.enums.common import Timeframe
from packages.observability.metrics.collectors import metrics

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Schemas ─────────────────────────────────────────────────

class IngestRequest(BaseModel):
    symbols: list[str]
    timeframe: str = "1D"


class QualityCheckRequest(BaseModel):
    instrument_id: Optional[uuid.UUID] = None


class JobRunResponse(BaseModel):
    id: uuid.UUID
    job_name: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    retries: int
    row_counts: Optional[dict]
    exception_details: Optional[str]


class DataIssueResponse(BaseModel):
    id: uuid.UUID
    instrument_id: Optional[uuid.UUID]
    issue_type: str
    severity: str
    description: str
    resolved: bool
    created_at: datetime


class IngestionStatusResponse(BaseModel):
    total_instruments: int
    active_instruments: int
    total_bars: int
    latest_bar_date: Optional[str]
    recent_jobs: list[dict]
    open_issues: int
    quality_score: float


# ── Endpoints ───────────────────────────────────────────────

@router.get("/status", response_model=IngestionStatusResponse)
async def get_system_status(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Get overall system and data status."""
    # Instrument counts
    total_inst = (await db.execute(select(func.count()).select_from(Instrument))).scalar()
    active_inst = (await db.execute(
        select(func.count()).select_from(Instrument).where(Instrument.status == "ACTIVE")
    )).scalar()

    # Bar counts
    total_bars = (await db.execute(select(func.count()).select_from(MarketBar))).scalar()

    # Latest bar
    latest = await db.execute(
        select(MarketBar.ts_open).order_by(desc(MarketBar.ts_open)).limit(1)
    )
    latest_date = latest.scalar()

    # Recent jobs
    jobs_result = await db.execute(
        select(JobRun).order_by(desc(JobRun.created_at)).limit(10)
    )
    recent_jobs = [
        {
            "name": j.job_name,
            "status": j.status,
            "started": j.started_at.isoformat(),
            "completed": j.completed_at.isoformat() if j.completed_at else None,
            "rows": j.row_counts,
        }
        for j in jobs_result.scalars().all()
    ]

    # Open issues
    open_issues = (await db.execute(
        select(func.count()).select_from(DataIssue).where(DataIssue.resolved == False)
    )).scalar()

    return IngestionStatusResponse(
        total_instruments=total_inst or 0,
        active_instruments=active_inst or 0,
        total_bars=total_bars or 0,
        latest_bar_date=latest_date.isoformat() if latest_date else None,
        recent_jobs=recent_jobs,
        open_issues=open_issues or 0,
        quality_score=1.0,  # placeholder
    )


@router.post("/ingest")
async def trigger_ingestion(
    req: IngestRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Manually trigger data ingestion for symbols."""
    provider = YahooFinanceProvider()
    pipeline = IngestionPipeline(provider)

    tf = Timeframe(req.timeframe)
    result = await pipeline.ingest_bars(db, req.symbols, tf)

    return {
        "status": result.status,
        "processed": result.rows_processed,
        "inserted": result.rows_inserted,
        "updated": result.rows_updated,
        "rejected": result.rows_rejected,
        "errors": result.errors,
        "quality_score": result.quality_report.score if result.quality_report else None,
    }


@router.post("/quality-check")
async def run_quality_check(
    req: QualityCheckRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Run data quality check on stored data."""
    provider = YahooFinanceProvider()
    pipeline = IngestionPipeline(provider)
    return await pipeline.run_quality_check(db, req.instrument_id)


@router.get("/jobs", response_model=list[JobRunResponse])
async def list_jobs(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """List recent job runs."""
    result = await db.execute(
        select(JobRun).order_by(desc(JobRun.created_at)).limit(limit)
    )
    return [
        JobRunResponse(
            id=j.id,
            job_name=j.job_name,
            status=j.status,
            started_at=j.started_at,
            completed_at=j.completed_at,
            retries=j.retries,
            row_counts=j.row_counts,
            exception_details=j.exception_details,
        )
        for j in result.scalars().all()
    ]


@router.get("/issues", response_model=list[DataIssueResponse])
async def list_issues(
    resolved: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """List data quality issues."""
    query = select(DataIssue).order_by(desc(DataIssue.created_at)).limit(limit)
    if resolved is not None:
        query = query.where(DataIssue.resolved == resolved)

    result = await db.execute(query)
    return [
        DataIssueResponse(
            id=i.id,
            instrument_id=i.instrument_id,
            issue_type=i.issue_type,
            severity=i.severity,
            description=i.description,
            resolved=i.resolved,
            created_at=i.created_at,
        )
        for i in result.scalars().all()
    ]


@router.get("/metrics")
async def get_metrics(
    _user: User = Depends(require_admin),
):
    """Get all collected metrics."""
    return metrics.get_all()
