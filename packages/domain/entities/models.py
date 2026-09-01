"""Core ORM models — all 18+ entities from the PRD Section 8."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    String, Text, Integer, Numeric, Boolean, DateTime, ForeignKey,
    Index, UniqueConstraint, CheckConstraint, Enum as SAEnum, JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from packages.domain.enums.common import (
    InstrumentType, InstrumentStatus, Timeframe, SignalState, Horizon,
    QualityGate, CorporateActionType, DataQualityStatus, BacktestStatus,
    PortfolioType, AlertChannel, UserRole,
)


# ── 1. Instrument ────────────────────────────────────────────
class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[InstrumentType] = mapped_column(SAEnum(InstrumentType), nullable=False)
    venue_id: Mapped[Optional[str]] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[InstrumentStatus] = mapped_column(
        SAEnum(InstrumentStatus), nullable=False, default=InstrumentStatus.ACTIVE
    )
    isin: Mapped[Optional[str]] = mapped_column(String(12))
    cusip: Mapped[Optional[str]] = mapped_column(String(9))
    figi: Mapped[Optional[str]] = mapped_column(String(12))
    exchange: Mapped[Optional[str]] = mapped_column(String(50))
    sector: Mapped[Optional[str]] = mapped_column(String(100))
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(3))
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    bars: Mapped[list["MarketBar"]] = relationship(back_populates="instrument")
    corporate_actions: Mapped[list["CorporateAction"]] = relationship(back_populates="instrument")
    fundamentals: Mapped[list["FundamentalFact"]] = relationship(back_populates="instrument")
    signals: Mapped[list["Signal"]] = relationship(back_populates="instrument")

    __table_args__ = (
        UniqueConstraint("symbol", "venue_id", name="uq_instrument_symbol_venue"),
        Index("ix_instrument_type_status", "type", "status"),
    )


# ── 2. Corporate Action ─────────────────────────────────────
class CorporateAction(Base):
    __tablename__ = "corporate_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    type: Mapped[CorporateActionType] = mapped_column(SAEnum(CorporateActionType), nullable=False)
    ex_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    record_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 10))
    cash_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    description: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_revision: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    instrument: Mapped["Instrument"] = relationship(back_populates="corporate_actions")

    __table_args__ = (
        Index("ix_corporate_action_instrument_date", "instrument_id", "ex_date"),
    )


# ── 3. Market Bar ───────────────────────────────────────────
class MarketBar(Base):
    __tablename__ = "market_bars"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    venue_id: Mapped[Optional[str]] = mapped_column(String(20))
    timeframe: Mapped[Timeframe] = mapped_column(SAEnum(Timeframe), nullable=False)
    ts_open: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ts_close: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Raw OHLCV
    open: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    vwap: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    trade_count: Mapped[Optional[int]] = mapped_column(Integer)
    # Adjusted values
    adj_open: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    adj_high: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    adj_low: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    adj_close: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    adjustment_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 10), default=Decimal("1.0"))
    # Metadata
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_revision: Mapped[Optional[str]] = mapped_column(String(100))
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))
    quality_status: Mapped[DataQualityStatus] = mapped_column(
        SAEnum(DataQualityStatus), default=DataQualityStatus.RAW
    )
    ingestion_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    instrument: Mapped["Instrument"] = relationship(back_populates="bars")

    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "timeframe", "ts_open", "source_revision",
            name="uq_bar_instrument_tf_ts_source"
        ),
        Index("ix_bar_instrument_timeframe_ts", "instrument_id", "timeframe", "ts_open"),
    )


# ── 4. Fundamental Fact ─────────────────────────────────────
class FundamentalFact(Base):
    __tablename__ = "fundamental_facts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    taxonomy: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "revenue", "pe_ratio"
    period: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g., "2024-Q1", "2024"
    filed_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    value: Mapped[Decimal] = mapped_column(Numeric(30, 10), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g., "USD", "ratio"
    accession: Mapped[Optional[str]] = mapped_column(String(50))  # SEC accession number
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    instrument: Mapped["Instrument"] = relationship(back_populates="fundamentals")

    __table_args__ = (
        UniqueConstraint("instrument_id", "taxonomy", "period", "source", name="uq_fundamental"),
        Index("ix_fundamental_instrument_taxonomy", "instrument_id", "taxonomy"),
    )


# ── 5. Data Snapshot ────────────────────────────────────────
class DataSnapshot(Base):
    __tablename__ = "data_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_versions: Mapped[dict] = mapped_column(JSON, nullable=False)
    cutoff_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hashes: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ── 6. Feature Definition ───────────────────────────────────
class FeatureDefinition(Base):
    __tablename__ = "feature_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    logic: Mapped[str] = mapped_column(Text, nullable=False)  # description or code reference
    parameters: Mapped[Optional[dict]] = mapped_column(JSON)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ── 7. Feature Value ────────────────────────────────────────
class FeatureValue(Base):
    __tablename__ = "feature_values"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_snapshots.id"), nullable=False
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    feature_def_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feature_definitions.id"), nullable=False
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(30, 10), nullable=False)
    quality: Mapped[QualityGate] = mapped_column(SAEnum(QualityGate), default=QualityGate.PASS)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("snapshot_id", "instrument_id", "feature_def_id", "ts", name="uq_feature_value"),
        Index("ix_feature_value_instrument_ts", "instrument_id", "ts"),
    )


# ── 8. Strategy Version ─────────────────────────────────────
class StrategyVersion(Base):
    __tablename__ = "strategy_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    horizon: Mapped[Horizon] = mapped_column(SAEnum(Horizon), nullable=False)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")  # DRAFT, VALIDATED, PROMOTED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    signals: Mapped[list["Signal"]] = relationship(back_populates="strategy_version")


# ── 9. Signal ───────────────────────────────────────────────
class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon: Mapped[Horizon] = mapped_column(SAEnum(Horizon), nullable=False)
    state: Mapped[SignalState] = mapped_column(SAEnum(SignalState), nullable=False)
    entry_zone_low: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    entry_zone_high: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    invalidation_rule: Mapped[Optional[str]] = mapped_column(Text)
    invalidation_level: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))
    target_method: Mapped[Optional[str]] = mapped_column(String(50))
    max_loss_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    suggested_size_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    quality_gate: Mapped[QualityGate] = mapped_column(SAEnum(QualityGate), nullable=False)
    strategy_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategy_versions.id"), nullable=False
    )
    data_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_snapshots.id"), nullable=False
    )
    evidence_ids: Mapped[Optional[list]] = mapped_column(JSON)
    reason_codes: Mapped[Optional[list]] = mapped_column(JSON)
    limitations: Mapped[Optional[list]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    instrument: Mapped["Instrument"] = relationship(back_populates="signals")
    strategy_version: Mapped["StrategyVersion"] = relationship(back_populates="signals")

    __table_args__ = (
        Index("ix_signal_instrument_as_of", "instrument_id", "as_of"),
        Index("ix_signal_state_horizon", "state", "horizon"),
    )


# ── 10. Backtest Run ────────────────────────────────────────
class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_snapshots.id"), nullable=False
    )
    strategy_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategy_versions.id"), nullable=False
    )
    assumptions: Mapped[dict] = mapped_column(JSON, nullable=False)
    metrics: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[BacktestStatus] = mapped_column(
        SAEnum(BacktestStatus), default=BacktestStatus.PENDING
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ── 11. Model Version ───────────────────────────────────────
class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    artifact_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    training_window: Mapped[dict] = mapped_column(JSON, nullable=False)
    features: Mapped[list] = mapped_column(JSON, nullable=False)
    metrics: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ── 12. Portfolio / Account ─────────────────────────────────
class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), default="USD")
    type: Mapped[PortfolioType] = mapped_column(SAEnum(PortfolioType), default=PortfolioType.PAPER)
    risk_policy: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    positions: Mapped[list["Position"]] = relationship(back_populates="portfolio")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="portfolio")


# ── 13. Transaction / Position ──────────────────────────────
class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # BUY, SELL
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signal_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("signals.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    portfolio: Mapped["Portfolio"] = relationship(back_populates="transactions")

    __table_args__ = (
        Index("ix_transaction_portfolio_ts", "portfolio_id", "ts"),
    )


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal("0"))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    portfolio: Mapped["Portfolio"] = relationship(back_populates="positions")

    __table_args__ = (
        UniqueConstraint("portfolio_id", "instrument_id", name="uq_position_portfolio_instrument"),
    )


# ── 14. Watchlist / Alert Rule ──────────────────────────────
class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    instrument_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    conditions: Mapped[dict] = mapped_column(JSON, nullable=False)
    channels: Mapped[list] = mapped_column(JSON, default=list)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ── 15. Evidence Item ───────────────────────────────────────
class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    excerpt: Mapped[Optional[str]] = mapped_column(Text)
    structured_fact: Mapped[Optional[dict]] = mapped_column(JSON)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_evidence_source_ts", "source", "ts"),
    )


# ── 16. Reasoning Run ───────────────────────────────────────
class ReasoningRun(Base):
    __tablename__ = "reasoning_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_versions.id")
    )
    template_version: Mapped[str] = mapped_column(String(20), nullable=False)
    tool_calls: Mapped[Optional[list]] = mapped_column(JSON)
    evidence_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    final_output: Mapped[str] = mapped_column(Text, nullable=False)
    validation_result: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ── 17. Audit Event ─────────────────────────────────────────
class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    before_hash: Mapped[Optional[str]] = mapped_column(String(64))
    after_hash: Mapped[Optional[str]] = mapped_column(String(64))
    trace_id: Mapped[Optional[str]] = mapped_column(String(64))
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_audit_actor_created", "actor_id", "created_at"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )


# ── 18. Job Run / Data Issue ────────────────────────────────
class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # RUNNING, SUCCESS, FAILED
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    retries: Mapped[int] = mapped_column(Integer, default=0)
    row_counts: Mapped[Optional[dict]] = mapped_column(JSON)
    exception_details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_job_run_name_started", "job_name", "started_at"),
    )


class DataIssue(Base):
    __tablename__ = "data_issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id")
    )
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    description: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


# ── 19. User (Auth) ─────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.VIEWER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
