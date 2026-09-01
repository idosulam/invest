"""Data ingestion pipeline — PRD Section 4.3.

Manages the data lifecycle:
1. Land raw payload
2. Validate schema and quality
3. Normalize identifiers
4. Apply adjustments
5. Publish data snapshot
6. Compute indicators

Designed to run as Prefect flows or standalone scripts.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.entities.models import (
    Instrument, MarketBar, CorporateAction, DataSnapshot,
    JobRun, DataIssue,
)
from packages.domain.enums.common import (
    Timeframe, DataQualityStatus, InstrumentStatus,
)
from packages.data.quality.validator import DataQualityValidator, QualityReport
from packages.data.providers.base import MarketDataProvider, BarsRequest


@dataclass
class IngestionResult:
    """Result of an ingestion run."""
    job_name: str
    status: str  # SUCCESS, PARTIAL, FAILED
    rows_processed: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_rejected: int = 0
    quality_report: Optional[QualityReport] = None
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class IngestionPipeline:
    """Orchestrates data ingestion from providers to database.

    Supports:
    - Daily/intraday bar ingestion
    - Corporate action ingestion
    - Instrument metadata refresh
    - Quality validation at each step
    """

    def __init__(self, provider: MarketDataProvider):
        self.provider = provider
        self.validator = DataQualityValidator()

    async def ingest_bars(
        self,
        db: AsyncSession,
        symbols: list[str],
        timeframe: Timeframe = Timeframe.DAILY,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> IngestionResult:
        """Ingest OHLCV bars for a list of symbols.

        Steps:
        1. Fetch bars from provider
        2. Validate quality
        3. Upsert into database
        4. Log job run
        """
        result = IngestionResult(job_name=f"ingest_bars_{timeframe.value}")

        try:
            # Step 1: Fetch from provider
            request = BarsRequest(symbols=symbols, timeframe=timeframe, start=start, end=end)
            bars = list(self.provider.bars(request))
            result.rows_processed = len(bars)

            if not bars:
                result.status = "SUCCESS"
                result.completed_at = datetime.utcnow()
                return result

            # Step 2: Validate quality
            df = pd.DataFrame([
                {
                    "ts_open": b.ts_open,
                    "open": float(b.open),
                    "high": float(b.high),
                    "low": float(b.low),
                    "close": float(b.close),
                    "volume": float(b.volume),
                }
                for b in bars
            ])
            quality = self.validator.validate_bars(df)
            result.quality_report = quality

            # Step 3: Upsert into database
            for bar in bars:
                try:
                    # Get instrument ID
                    inst_result = await db.execute(
                        select(Instrument).where(Instrument.symbol == bar.symbol)
                    )
                    instrument = inst_result.scalar_one_or_none()
                    if not instrument:
                        result.errors.append(f"Instrument not found: {bar.symbol}")
                        result.rows_rejected += 1
                        continue

                    # Check for existing bar
                    existing = await db.execute(
                        select(MarketBar).where(
                            MarketBar.instrument_id == instrument.id,
                            MarketBar.timeframe == timeframe,
                            MarketBar.ts_open == bar.ts_open,
                        )
                    )
                    existing_bar = existing.scalar_one_or_none()

                    if existing_bar:
                        # Update if price changed
                        if (
                            float(existing_bar.close) != float(bar.close)
                            or float(existing_bar.volume) != float(bar.volume)
                        ):
                            existing_bar.open = bar.open
                            existing_bar.high = bar.high
                            existing_bar.low = bar.low
                            existing_bar.close = bar.close
                            existing_bar.volume = bar.volume
                            existing_bar.quality_status = DataQualityStatus.VALIDATED
                            result.rows_updated += 1
                    else:
                        # Insert new bar
                        new_bar = MarketBar(
                            instrument_id=instrument.id,
                            timeframe=timeframe,
                            ts_open=bar.ts_open,
                            ts_close=bar.ts_close,
                            open=bar.open,
                            high=bar.high,
                            low=bar.low,
                            close=bar.close,
                            volume=bar.volume,
                            vwap=bar.vwap,
                            currency=bar.currency,
                            source=self.provider.name,
                            quality_status=DataQualityStatus.VALIDATED,
                        )
                        db.add(new_bar)
                        result.rows_inserted += 1

                except Exception as e:
                    result.errors.append(f"Error processing {bar.symbol}: {str(e)}")
                    result.rows_rejected += 1

            await db.flush()

            # Step 4: Log job run
            job_run = JobRun(
                job_name=result.job_name,
                status="SUCCESS" if not result.errors else "PARTIAL",
                started_at=result.started_at,
                completed_at=datetime.utcnow(),
                row_counts={
                    "processed": result.rows_processed,
                    "inserted": result.rows_inserted,
                    "updated": result.rows_updated,
                    "rejected": result.rows_rejected,
                },
                exception_details="\n".join(result.errors) if result.errors else None,
            )
            db.add(job_run)
            await db.flush()

            result.status = "SUCCESS" if not result.errors else "PARTIAL"
            result.completed_at = datetime.utcnow()

        except Exception as e:
            result.status = "FAILED"
            result.errors.append(str(e))
            result.completed_at = datetime.utcnow()

            # Log failed job
            job_run = JobRun(
                job_name=result.job_name,
                status="FAILED",
                started_at=result.started_at,
                completed_at=datetime.utcnow(),
                exception_details=str(e),
            )
            db.add(job_run)
            await db.flush()

        return result

    async def ingest_instruments(
        self,
        db: AsyncSession,
        symbols: list[str],
    ) -> IngestionResult:
        """Ingest instrument metadata from provider."""
        result = IngestionResult(job_name="ingest_instruments")

        for symbol in symbols:
            try:
                info = self.provider.get_instrument_info(symbol)
                if not info:
                    result.errors.append(f"No data for {symbol}")
                    result.rows_rejected += 1
                    continue

                existing = await db.execute(
                    select(Instrument).where(Instrument.symbol == info.symbol)
                )
                instrument = existing.scalar_one_or_none()

                if instrument:
                    instrument.name = info.name
                    instrument.type = info.type
                    instrument.exchange = info.exchange
                    instrument.sector = info.sector
                    instrument.industry = info.industry
                    instrument.country = info.country
                    result.rows_updated += 1
                else:
                    new_inst = Instrument(
                        symbol=info.symbol,
                        name=info.name,
                        type=info.type,
                        exchange=info.exchange,
                        currency=info.currency,
                        sector=info.sector,
                        industry=info.industry,
                        country=info.country,
                        status=InstrumentStatus.ACTIVE,
                    )
                    db.add(new_inst)
                    result.rows_inserted += 1

                result.rows_processed += 1

            except Exception as e:
                result.errors.append(f"{symbol}: {str(e)}")
                result.rows_rejected += 1

        await db.flush()
        result.status = "SUCCESS" if not result.errors else "PARTIAL"
        result.completed_at = datetime.utcnow()
        return result

    async def run_quality_check(
        self,
        db: AsyncSession,
        instrument_id: Optional[uuid.UUID] = None,
    ) -> dict:
        """Run quality checks on stored data.

        Returns summary of quality issues found.
        """
        query = select(MarketBar).order_by(MarketBar.ts_open)
        if instrument_id:
            query = query.where(MarketBar.instrument_id == instrument_id)

        result = await db.execute(query.limit(10000))
        bars = result.scalars().all()

        if not bars:
            return {"status": "no_data", "issues": []}

        df = pd.DataFrame([
            {
                "ts_open": b.ts_open,
                "open": float(b.open),
                "high": float(b.high),
                "low": float(b.low),
                "close": float(b.close),
                "volume": float(b.volume),
            }
            for b in bars
        ])

        report = self.validator.validate_bars(df)

        # Persist issues
        for issue in report.issues:
            if issue.severity in ("HIGH", "CRITICAL"):
                data_issue = DataIssue(
                    instrument_id=instrument_id,
                    issue_type=issue.issue_type,
                    severity=issue.severity,
                    description=issue.description,
                )
                db.add(data_issue)

        await db.flush()

        return {
            "status": "passed" if report.passed else "failed",
            "score": report.score,
            "rows_checked": report.rows_checked,
            "issues": [
                {
                    "type": i.issue_type,
                    "severity": i.severity,
                    "description": i.description,
                    "affected_rows": i.affected_rows,
                }
                for i in report.issues
            ],
        }
