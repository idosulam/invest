"""Alert rules endpoints — PRD Section 1.3 (alerts).

CRUD for alert rules with condition evaluation.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import get_current_user
from apps.api.database import get_db
from packages.domain.entities.models import AlertRule, User
from packages.domain.enums.common import AlertChannel

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ── Schemas ─────────────────────────────────────────────────

class AlertRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    conditions: dict = Field(..., description="Alert conditions, e.g. {\"type\": \"rsi_below\", \"instrument_id\": \"...\", \"threshold\": 30}")
    channels: list[AlertChannel] = [AlertChannel.IN_APP]
    cooldown_minutes: int = Field(60, ge=1, le=10080)


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    conditions: Optional[dict] = None
    channels: Optional[list[AlertChannel]] = None
    cooldown_minutes: Optional[int] = None
    enabled: Optional[bool] = None


class AlertRuleResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    conditions: dict
    channels: list[str]
    cooldown_minutes: int
    enabled: bool
    last_fired_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Endpoints ───────────────────────────────────────────────

@router.get("", response_model=list[AlertRuleResponse])
async def list_alert_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List alert rules owned by the current user."""
    result = await db.execute(
        select(AlertRule)
        .where(AlertRule.owner_id == current_user.id)
        .order_by(AlertRule.name)
    )
    return [AlertRuleResponse.model_validate(r) for r in result.scalars().all()]


@router.post("", response_model=AlertRuleResponse, status_code=201)
async def create_alert_rule(
    req: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new alert rule."""
    rule = AlertRule(
        owner_id=current_user.id,
        name=req.name,
        conditions=req.conditions,
        channels=[c.value for c in req.channels],
        cooldown_minutes=req.cooldown_minutes,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


@router.get("/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AlertRule).where(
            AlertRule.id == rule_id,
            AlertRule.owner_id == current_user.id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return rule


@router.patch("/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: uuid.UUID,
    req: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an alert rule."""
    result = await db.execute(
        select(AlertRule).where(
            AlertRule.id == rule_id,
            AlertRule.owner_id == current_user.id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    if req.name is not None:
        rule.name = req.name
    if req.conditions is not None:
        rule.conditions = req.conditions
    if req.channels is not None:
        rule.channels = [c.value for c in req.channels]
    if req.cooldown_minutes is not None:
        rule.cooldown_minutes = req.cooldown_minutes
    if req.enabled is not None:
        rule.enabled = req.enabled

    await db.flush()
    await db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
async def delete_alert_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AlertRule).where(
            AlertRule.id == rule_id,
            AlertRule.owner_id == current_user.id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    await db.delete(rule)
