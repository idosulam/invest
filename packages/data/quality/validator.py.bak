"""Data quality validator — PRD Section 4.3.

Validates data at each stage of the ingestion pipeline:
1. Schema validation
2. Timezone and timestamp checks
3. Price relationship checks (high >= low, etc.)
4. Duplicate detection
5. Monotonic timestamp verification
6. Staleness detection
7. Completeness checks
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import pandas as pd


@dataclass
class QualityIssue:
    """A detected data quality issue."""
    issue_type: str  # schema, price, duplicate, stale, missing, monotonic
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    description: str
    affected_rows: int = 0
    details: dict = field(default_factory=dict)


@dataclass
class QualityReport:
    """Result of a quality validation pass."""
    passed: bool
    score: float  # 0.0 - 1.0
    issues: list[QualityIssue] = field(default_factory=list)
    rows_checked: int = 0
    rows_passed: int = 0
    rows_failed: int = 0
    checked_at: datetime = field(default_factory=datetime.utcnow)


class DataQualityValidator:
    """Validates market data quality.

    PRD 4.3 requirements:
    - Validate schema, timezone, price relationships, duplicates
    - Check monotonic timestamps
    - Detect stale data
    - Report completeness
    """

    def __init__(
        self,
        max_staleness_hours: int = 48,
        min_completeness: float = 0.95,
        max_gap_ratio: float = 0.05,
    ):
        self.max_staleness = timedelta(hours=max_staleness_hours)
        self.min_completeness = min_completeness
        self.max_gap_ratio = max_gap_ratio

    def validate_bars(self, df: pd.DataFrame) -> QualityReport:
        """Validate a DataFrame of OHLCV bars.

        Args:
            df: DataFrame with columns: ts_open, open, high, low, close, volume

        Returns:
            QualityReport with issues and score
        """
        issues = []
        rows_checked = len(df)

        if rows_checked == 0:
            return QualityReport(
                passed=False, score=0, rows_checked=0,
                issues=[QualityIssue("schema", "CRITICAL", "No data to validate")],
            )

        # 1. Schema check
        required_cols = {"ts_open", "open", "high", "low", "close", "volume"}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            issues.append(QualityIssue(
                "schema", "CRITICAL",
                f"Missing columns: {missing_cols}",
                details={"missing": list(missing_cols)},
            ))
            return QualityReport(passed=False, score=0, rows_checked=rows_checked, issues=issues)

        # 2. Null check
        null_counts = df[list(required_cols - {"ts_open"})].isnull().sum()
        total_nulls = null_counts.sum()
        if total_nulls > 0:
            severity = "HIGH" if total_nulls > rows_checked * 0.1 else "MEDIUM"
            issues.append(QualityIssue(
                "schema", severity,
                f"Null values found: {null_counts.to_dict()}",
                affected_rows=int(null_counts.max()),
            ))

        # 3. Price relationship checks
        price_issues = 0
        if "high" in df.columns and "low" in df.columns:
            # High must be >= Low
            bad_hl = df[df["high"] < df["low"]]
            if len(bad_hl) > 0:
                price_issues += len(bad_hl)
                issues.append(QualityIssue(
                    "price", "HIGH",
                    f"{len(bad_hl)} bars where high < low",
                    affected_rows=len(bad_hl),
                ))

        if "high" in df.columns and "open" in df.columns:
            # High must be >= Open
            bad_ho = df[df["high"] < df["open"]]
            if len(bad_ho) > 0:
                price_issues += len(bad_ho)

        if "high" in df.columns and "close" in df.columns:
            # High must be >= Close
            bad_hc = df[df["high"] < df["close"]]
            if len(bad_hc) > 0:
                price_issues += len(bad_hc)

        if "low" in df.columns and "open" in df.columns:
            # Low must be <= Open
            bad_lo = df[df["low"] > df["open"]]
            if len(bad_lo) > 0:
                price_issues += len(bad_lo)

        if "low" in df.columns and "close" in df.columns:
            # Low must be <= Close
            bad_lc = df[df["low"] > df["close"]]
            if len(bad_lc) > 0:
                price_issues += len(bad_lc)

        if price_issues > 0:
            issues.append(QualityIssue(
                "price", "HIGH",
                f"Total price relationship violations: {price_issues}",
                affected_rows=price_issues,
            ))

        # 4. Negative prices
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                neg = (df[col] < 0).sum()
                if neg > 0:
                    issues.append(QualityIssue(
                        "price", "CRITICAL",
                        f"{neg} negative values in {col}",
                        affected_rows=int(neg),
                    ))

        # 5. Zero volume check
        if "volume" in df.columns:
            zero_vol = (df["volume"] == 0).sum()
            if zero_vol > rows_checked * 0.5:
                issues.append(QualityIssue(
                    "price", "MEDIUM",
                    f"{zero_vol} bars with zero volume ({zero_vol/rows_checked*100:.0f}%)",
                    affected_rows=int(zero_vol),
                ))

        # 6. Duplicate timestamps
        if "ts_open" in df.columns:
            dupes = df["ts_open"].duplicated().sum()
            if dupes > 0:
                issues.append(QualityIssue(
                    "duplicate", "HIGH",
                    f"{dupes} duplicate timestamps",
                    affected_rows=int(dupes),
                ))

        # 7. Monotonic timestamps
        if "ts_open" in df.columns and len(df) > 1:
            ts = pd.to_datetime(df["ts_open"])
            non_monotonic = (ts.diff() < timedelta(0)).sum()
            if non_monotonic > 0:
                issues.append(QualityIssue(
                    "monotonic", "HIGH",
                    f"{non_monotonic} non-monotonic timestamp transitions",
                    affected_rows=int(non_monotonic),
                ))

        # 8. Staleness check
        if "ts_open" in df.columns and len(df) > 0:
            latest = pd.to_datetime(df["ts_open"]).max()
            age = datetime.utcnow() - latest.to_pydatetime()
            if age > self.max_staleness:
                issues.append(QualityIssue(
                    "stale", "HIGH",
                    f"Data is stale: latest bar is {age.days}d {age.seconds // 3600}h old",
                    details={"latest": str(latest), "max_staleness_hours": self.max_staleness.total_seconds() / 3600},
                ))

        # 9. Gap detection (missing trading days)
        if "ts_open" in df.columns and len(df) > 5:
            ts = pd.to_datetime(df["ts_open"]).sort_values()
            gaps = ts.diff()
            median_gap = gaps.median()
            large_gaps = gaps[gaps > median_gap * 3]
            if len(large_gaps) > 0:
                gap_ratio = len(large_gaps) / len(df)
                if gap_ratio > self.max_gap_ratio:
                    issues.append(QualityIssue(
                        "missing", "MEDIUM",
                        f"{len(large_gaps)} large gaps detected ({gap_ratio*100:.1f}% of bars)",
                        affected_rows=len(large_gaps),
                    ))

        # 10. Extreme moves (>20% in a single bar)
        if "close" in df.columns and "open" in df.columns and len(df) > 1:
            pct_change = abs((df["close"] - df["open"]) / df["open"])
            extreme = (pct_change > 0.20).sum()
            if extreme > 0:
                issues.append(QualityIssue(
                    "price", "MEDIUM",
                    f"{extreme} bars with >20% intraday move",
                    affected_rows=int(extreme),
                ))

        # Calculate score
        rows_failed = sum(i.affected_rows for i in issues)
        rows_passed = rows_checked - rows_failed
        score = rows_passed / rows_checked if rows_checked > 0 else 0

        # Determine pass/fail
        critical = any(i.severity == "CRITICAL" for i in issues)
        high_count = sum(1 for i in issues if i.severity == "HIGH")
        passed = not critical and high_count <= 1 and score >= self.min_completeness

        return QualityReport(
            passed=passed,
            score=round(score, 4),
            issues=issues,
            rows_checked=rows_checked,
            rows_passed=rows_passed,
            rows_failed=rows_failed,
        )

    def validate_instruments(self, df: pd.DataFrame) -> QualityReport:
        """Validate instrument metadata."""
        issues = []
        rows_checked = len(df)

        if rows_checked == 0:
            return QualityReport(passed=True, score=1.0, rows_checked=0)

        # Check required fields
        for col in ["symbol", "name", "type"]:
            if col not in df.columns:
                issues.append(QualityIssue("schema", "CRITICAL", f"Missing column: {col}"))
            else:
                nulls = df[col].isnull().sum()
                if nulls > 0:
                    issues.append(QualityIssue("schema", "HIGH", f"{nulls} null {col} values", affected_rows=int(nulls)))

        # Duplicate symbols
        if "symbol" in df.columns:
            dupes = df["symbol"].duplicated().sum()
            if dupes > 0:
                issues.append(QualityIssue("duplicate", "HIGH", f"{dupes} duplicate symbols", affected_rows=int(dupes)))

        rows_failed = sum(i.affected_rows for i in issues)
        score = (rows_checked - rows_failed) / rows_checked if rows_checked > 0 else 1.0

        return QualityReport(
            passed=not any(i.severity == "CRITICAL" for i in issues),
            score=round(score, 4),
            issues=issues,
            rows_checked=rows_checked,
            rows_passed=rows_checked - rows_failed,
            rows_failed=rows_failed,
        )
