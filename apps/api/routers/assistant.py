"""Assistant / Reasoning endpoints — PRD Section 7.

LLM-powered explanation layer with evidence-based reasoning.
All tool calls are allowlisted, read-only, and schema-validated.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import get_current_user
from apps.api.database import get_db
from packages.domain.entities.models import ReasoningRun, User
from packages.reasoning.engine import ReasoningEngine, ExplanationRequest

router = APIRouter(prefix="/assistant", tags=["assistant"])

engine = ReasoningEngine()


# ── Schemas ─────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    instrument_id: uuid.UUID
    context_type: str = "signal"  # signal, backtest, general


class ExplanationResponse(BaseModel):
    id: str
    question: str
    answer: str
    evidence_ids: list[str]
    evidence_summary: dict
    validation: dict
    tool_calls: list[dict]
    created_at: str


class ReasoningRunResponse(BaseModel):
    id: uuid.UUID
    template_version: str
    tool_calls: Optional[list]
    evidence_ids: list
    final_output: str
    validation_result: dict
    created_at: datetime


# ── Endpoints ───────────────────────────────────────────────

@router.post("/query", response_model=ExplanationResponse)
async def query_assistant(
    req: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ask the assistant a question about an instrument.

    The assistant retrieves evidence from stored data, generates
    an explanation, and validates the output.
    """
    request = ExplanationRequest(
        question=req.question,
        instrument_id=req.instrument_id,
        context_type=req.context_type,
    )

    result = await engine.explain(db, request)

    # Persist reasoning run
    run = ReasoningRun(
        template_version=result.template_version,
        tool_calls=result.tool_calls,
        evidence_ids=result.evidence_ids,
        final_output=result.answer,
        validation_result={
            "valid": result.validation.valid,
            "errors": result.validation.errors,
            "warnings": result.validation.warnings,
        },
    )
    db.add(run)
    await db.flush()

    return ExplanationResponse(
        id=result.id,
        question=result.question,
        answer=result.answer,
        evidence_ids=result.evidence_ids,
        evidence_summary=result.evidence_summary,
        validation={
            "valid": result.validation.valid,
            "errors": result.validation.errors,
            "warnings": result.validation.warnings,
        },
        tool_calls=result.tool_calls,
        created_at=result.created_at.isoformat(),
    )


@router.get("/history", response_model=list[ReasoningRunResponse])
async def get_reasoning_history(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get recent reasoning runs."""
    result = await db.execute(
        select(ReasoningRun).order_by(desc(ReasoningRun.created_at)).limit(limit)
    )
    runs = result.scalars().all()

    return [
        ReasoningRunResponse(
            id=r.id,
            template_version=r.template_version,
            tool_calls=r.tool_calls,
            evidence_ids=r.evidence_ids,
            final_output=r.final_output,
            validation_result=r.validation_result,
            created_at=r.created_at,
        )
        for r in runs
    ]
