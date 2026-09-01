"""Metrics collectors — PRD Section 11.

Key metrics: ingestion lag, missing bars, revisions, job failures,
signal counts, abstentions, drift, backtest duration, API latency.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import time


@dataclass
class MetricPoint:
    """A single metric measurement."""
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MetricsCollector:
    """In-memory metrics collector for MVP.

    In production, export to Prometheus via prometheus_client.
    """

    def __init__(self):
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._recent: list[MetricPoint] = []

    # ── Counters ────────────────────────────────────────────

    def inc(self, name: str, value: float = 1, labels: Optional[dict] = None):
        """Increment a counter."""
        key = self._key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + value
        self._record(name, self._counters[key], labels)

    def get_counter(self, name: str, labels: Optional[dict] = None) -> float:
        return self._counters.get(self._key(name, labels), 0)

    # ── Gauges ──────────────────────────────────────────────

    def set_gauge(self, name: str, value: float, labels: Optional[dict] = None):
        """Set a gauge value."""
        key = self._key(name, labels)
        self._gauges[key] = value
        self._record(name, value, labels)

    def get_gauge(self, name: str, labels: Optional[dict] = None) -> float:
        return self._gauges.get(self._key(name, labels), 0)

    # ── Histograms ──────────────────────────────────────────

    def observe(self, name: str, value: float, labels: Optional[dict] = None):
        """Record a histogram observation."""
        key = self._key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        self._record(name, value, labels)

    def get_histogram(self, name: str, labels: Optional[dict] = None) -> dict:
        """Get histogram stats (count, sum, avg, p50, p95, p99)."""
        values = self._histograms.get(self._key(name, labels), [])
        if not values:
            return {"count": 0, "sum": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}
        sorted_v = sorted(values)
        n = len(sorted_v)
        return {
            "count": n,
            "sum": round(sum(sorted_v), 3),
            "avg": round(sum(sorted_v) / n, 3),
            "p50": round(sorted_v[n // 2], 3),
            "p95": round(sorted_v[int(n * 0.95)], 3) if n > 1 else round(sorted_v[0], 3),
            "p99": round(sorted_v[int(n * 0.99)], 3) if n > 1 else round(sorted_v[0], 3),
        }

    # ── Timer context manager ───────────────────────────────

    def timer(self, name: str, labels: Optional[dict] = None):
        """Context manager to time an operation."""
        return _Timer(self, name, labels)

    # ── Recent metrics ──────────────────────────────────────

    def get_recent(self, limit: int = 100) -> list[dict]:
        """Get recent metric points."""
        return [
            {"name": m.name, "value": m.value, "labels": m.labels, "ts": m.timestamp.isoformat()}
            for m in self._recent[-limit:]
        ]

    def get_all(self) -> dict:
        """Get all current metric values."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {k: self.get_histogram(k.split("|")[0], None) for k in self._histograms},
        }

    # ── Internal ────────────────────────────────────────────

    def _key(self, name: str, labels: Optional[dict]) -> str:
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{name}|{label_str}"
        return name

    def _record(self, name: str, value: float, labels: Optional[dict]):
        self._recent.append(MetricPoint(name=name, value=value, labels=labels or {}))
        if len(self._recent) > 10000:
            self._recent = self._recent[-5000:]


class _Timer:
    """Timer context manager."""

    def __init__(self, collector: MetricsCollector, name: str, labels: Optional[dict]):
        self.collector = collector
        self.name = name
        self.labels = labels
        self.start = 0

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        elapsed = time.time() - self.start
        self.collector.observe(self.name, elapsed, self.labels)


# ── Global instance ─────────────────────────────────────────

metrics = MetricsCollector()


# ── Pre-defined metric names ────────────────────────────────

class M:
    """Metric name constants."""
    # API
    API_REQUEST_DURATION = "api_request_duration_seconds"
    API_REQUEST_COUNT = "api_request_total"
    API_ERROR_COUNT = "api_error_total"

    # Data ingestion
    INGESTION_LAG_SECONDS = "ingestion_lag_seconds"
    INGESTION_ROWS_PROCESSED = "ingestion_rows_processed_total"
    INGESTION_ERRORS = "ingestion_errors_total"
    BARS_MISSING_COUNT = "bars_missing_count"
    BARS_REVISION_COUNT = "bars_revision_count"

    # Signals
    SIGNALS_GENERATED = "signals_generated_total"
    SIGNALS_BY_STATE = "signals_by_state"
    SIGNALS_SUPPRESSED = "signals_suppressed_total"

    # Backtests
    BACKTEST_DURATION = "backtest_duration_seconds"
    BACKTEST_COUNT = "backtest_runs_total"

    # Jobs
    JOB_DURATION = "job_duration_seconds"
    JOB_SUCCESS = "job_success_total"
    JOB_FAILURE = "job_failure_total"

    # Data quality
    DATA_QUALITY_SCORE = "data_quality_score"
    DATA_ISSUES_COUNT = "data_issues_count"

    # LLM
    LLM_QUERY_DURATION = "llm_query_duration_seconds"
    LLM_VALIDATION_FAILURES = "llm_validation_failures_total"
