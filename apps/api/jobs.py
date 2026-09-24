"""Background analysis jobs (#5) — run the heavy LLM pipeline off the request.

Fixes "the app gets stuck": instead of awaiting the full Ollama chain inline,
we spin up an asyncio task, record a JobRun (status + started_at + completed_at)
so the UI can show a "last run" timestamp, and let the frontend poll for status.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import desc, select

from apps.api.database import async_session_factory
from packages.domain.entities.models import JobRun
from packages.agents.consolidate import run_consolidated_analysis
from packages.portfolio.context import get_position_context

# In-memory job registry (single-process MVP). Status/last-run also persist to
# JobRun so the "last run" badge survives restarts.
_jobs: dict[str, dict] = {}


def _serialize(signal) -> dict:
    try:
        return signal.model_dump(mode="json")
    except Exception:
        return {"symbol": getattr(signal, "symbol", "?"), "error": "serialize failed"}


async def _run_analysis_job(
    job_id: str, scope: str, instrument_ids: list, user_id, target_weight: float
) -> None:
    job = _jobs[job_id]
    results: list[dict] = []
    total = len(instrument_ids)
    try:
        for i, inst_id in enumerate(instrument_ids):
            job["progress"] = {"done": i, "total": total}
            async with async_session_factory() as db:
                qty, avg_cost, pf_value = await get_position_context(db, user_id, inst_id)
                sig = await run_consolidated_analysis(
                    db,
                    inst_id,
                    position_qty=qty,
                    avg_cost=avg_cost,
                    portfolio_value=pf_value,
                    target_weight=target_weight,
                )
                results.append(_serialize(sig))
        job["status"] = "SUCCESS"
        job["results"] = results
    except Exception as e:  # noqa: BLE001
        job["status"] = "FAILED"
        job["error"] = str(e)
    finally:
        job["completed_at"] = datetime.utcnow().isoformat()
        job["progress"] = {"done": len(results) or total, "total": total}
        try:
            async with async_session_factory() as db:
                row = (
                    await db.execute(select(JobRun).where(JobRun.id == uuid.UUID(job_id)))
                ).scalar_one_or_none()
                if row:
                    row.status = job["status"]
                    row.completed_at = datetime.utcnow()
                    row.row_counts = {"instruments": len(results)}
                    if job.get("error"):
                        row.exception_details = job["error"]
                    await db.commit()
        except Exception:  # noqa: BLE001
            pass


async def start_analysis_job(
    scope: str, instrument_ids: list, user_id, target_weight: float = 0.05
) -> dict:
    job_id = str(uuid.uuid4())
    job_name = f"analysis_{scope}"
    now = datetime.utcnow()

    async with async_session_factory() as db:
        db.add(JobRun(id=uuid.UUID(job_id), job_name=job_name, status="RUNNING", started_at=now))
        await db.commit()

    _jobs[job_id] = {
        "job_id": job_id,
        "job_name": job_name,
        "scope": scope,
        "status": "RUNNING",
        "started_at": now.isoformat(),
        "completed_at": None,
        "progress": {"done": 0, "total": len(instrument_ids)},
        "results": None,
        "error": None,
    }
    asyncio.create_task(
        _run_analysis_job(job_id, scope, instrument_ids, user_id, target_weight)
    )
    return _jobs[job_id]


def get_job(job_id: str) -> Optional[dict]:
    return _jobs.get(job_id)


async def last_run(scope: str) -> dict:
    job_name = f"analysis_{scope}"
    async with async_session_factory() as db:
        q = await db.execute(
            select(JobRun)
            .where(JobRun.job_name == job_name)
            .order_by(desc(JobRun.started_at))
            .limit(1)
        )
        row = q.scalar_one_or_none()
    if not row:
        return {"scope": scope, "last_run_at": None, "last_status": None, "last_job_id": None}
    ts = (row.completed_at or row.started_at).isoformat()
    return {"scope": scope, "last_run_at": ts, "last_status": row.status, "last_job_id": str(row.id)}
