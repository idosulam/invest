"""Alert engine — PRD Section 1.3.

Evaluates alert rules against current market data and sends
notifications through configured channels.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Any

try:
    import structlog
    logger = structlog.get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


@dataclass
class AlertCondition:
    """Parsed alert condition."""
    type: str  # rsi_below, rsi_above, price_above, price_below, sma_cross, volume_surge
    instrument_id: Optional[str] = None
    threshold: Optional[float] = None
    params: dict = field(default_factory=dict)


@dataclass
class AlertTrigger:
    """Result of alert evaluation."""
    alert_rule_id: uuid.UUID
    instrument_id: Optional[uuid.UUID]
    condition_type: str
    message: str
    severity: str  # INFO, WARNING, CRITICAL
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    data: dict = field(default_factory=dict)


class AlertEngine:
    """Evaluates alert rules and manages notifications.

    Supported condition types:
    - rsi_below / rsi_above: RSI threshold alerts
    - price_above / price_below: Price level alerts
    - sma_cross: SMA crossover alerts
    - volume_surge: Volume spike detection
    - signal_change: New signal generated
    - data_staleness: Data freshness alerts
    """

    def __init__(self):
        self._handlers: dict[str, list] = {
            "IN_APP": [],
            "EMAIL": [],
            "WEBHOOK": [],
        }

    def register_handler(self, channel: str, handler):
        """Register a notification handler for a channel."""
        if channel in self._handlers:
            self._handlers[channel].append(handler)

    def evaluate_condition(
        self,
        condition: AlertCondition,
        current_data: dict[str, Any],
    ) -> Optional[AlertTrigger]:
        """Evaluate a single condition against current data.

        Args:
            condition: The alert condition to evaluate.
            current_data: Dict with current market data.
                Expected keys depend on condition type.

        Returns:
            AlertTrigger if condition is met, None otherwise.
        """
        cond_type = condition.type

        if cond_type == "rsi_below":
            rsi = current_data.get("rsi_14")
            if rsi is not None and rsi < condition.threshold:
                return AlertTrigger(
                    alert_rule_id=uuid.uuid4(),
                    instrument_id=uuid.UUID(condition.instrument_id) if condition.instrument_id else None,
                    condition_type=cond_type,
                    message=f"RSI({rsi:.1f}) below {condition.threshold}",
                    severity="WARNING",
                    data={"rsi": rsi, "threshold": condition.threshold},
                )

        elif cond_type == "rsi_above":
            rsi = current_data.get("rsi_14")
            if rsi is not None and rsi > condition.threshold:
                return AlertTrigger(
                    alert_rule_id=uuid.uuid4(),
                    instrument_id=uuid.UUID(condition.instrument_id) if condition.instrument_id else None,
                    condition_type=cond_type,
                    message=f"RSI({rsi:.1f}) above {condition.threshold}",
                    severity="WARNING",
                    data={"rsi": rsi, "threshold": condition.threshold},
                )

        elif cond_type == "price_above":
            price = current_data.get("close")
            if price is not None and price > condition.threshold:
                return AlertTrigger(
                    alert_rule_id=uuid.uuid4(),
                    instrument_id=uuid.UUID(condition.instrument_id) if condition.instrument_id else None,
                    condition_type=cond_type,
                    message=f"Price(${price:.2f}) above ${condition.threshold:.2f}",
                    severity="INFO",
                    data={"price": price, "threshold": condition.threshold},
                )

        elif cond_type == "price_below":
            price = current_data.get("close")
            if price is not None and price < condition.threshold:
                return AlertTrigger(
                    alert_rule_id=uuid.uuid4(),
                    instrument_id=uuid.UUID(condition.instrument_id) if condition.instrument_id else None,
                    condition_type=cond_type,
                    message=f"Price(${price:.2f}) below ${condition.threshold:.2f}",
                    severity="WARNING",
                    data={"price": price, "threshold": condition.threshold},
                )

        elif cond_type == "volume_surge":
            vol_ratio = current_data.get("volume_ratio", 1.0)
            threshold = condition.threshold or 2.0
            if vol_ratio > threshold:
                return AlertTrigger(
                    alert_rule_id=uuid.uuid4(),
                    instrument_id=uuid.UUID(condition.instrument_id) if condition.instrument_id else None,
                    condition_type=cond_type,
                    message=f"Volume surge: {vol_ratio:.1f}x average",
                    severity="INFO",
                    data={"volume_ratio": vol_ratio, "threshold": threshold},
                )

        elif cond_type == "sma_cross":
            sma_fast = current_data.get("sma_fast")
            sma_slow = current_data.get("sma_slow")
            sma_fast_prev = current_data.get("sma_fast_prev")
            sma_slow_prev = current_data.get("sma_slow_prev")
            if all(v is not None for v in [sma_fast, sma_slow, sma_fast_prev, sma_slow_prev]):
                if sma_fast_prev <= sma_slow_prev and sma_fast > sma_slow:
                    return AlertTrigger(
                        alert_rule_id=uuid.uuid4(),
                        instrument_id=uuid.UUID(condition.instrument_id) if condition.instrument_id else None,
                        condition_type=cond_type,
                        message=f"Golden cross: SMA({condition.params.get('fast', 20)}) crossed above SMA({condition.params.get('slow', 50)})",
                        severity="INFO",
                        data={"cross_type": "golden"},
                    )
                elif sma_fast_prev >= sma_slow_prev and sma_fast < sma_slow:
                    return AlertTrigger(
                        alert_rule_id=uuid.uuid4(),
                        instrument_id=uuid.UUID(condition.instrument_id) if condition.instrument_id else None,
                        condition_type=cond_type,
                        message=f"Death cross: SMA({condition.params.get('fast', 20)}) crossed below SMA({condition.params.get('slow', 50)})",
                        severity="WARNING",
                        data={"cross_type": "death"},
                    )

        elif cond_type == "signal_change":
            new_signal = current_data.get("new_signal")
            if new_signal:
                return AlertTrigger(
                    alert_rule_id=uuid.uuid4(),
                    instrument_id=uuid.UUID(condition.instrument_id) if condition.instrument_id else None,
                    condition_type=cond_type,
                    message=f"New signal: {new_signal}",
                    severity="INFO",
                    data={"signal": new_signal},
                )

        return None

    def parse_condition(self, raw: dict) -> AlertCondition:
        """Parse raw condition dict into AlertCondition."""
        return AlertCondition(
            type=raw.get("type", ""),
            instrument_id=raw.get("instrument_id"),
            threshold=raw.get("threshold"),
            params=raw.get("params", {}),
        )

    async def send_notification(
        self,
        trigger: AlertTrigger,
        channels: list[str],
    ):
        """Send alert notification through specified channels."""
        for channel in channels:
            handlers = self._handlers.get(channel, [])
            for handler in handlers:
                try:
                    await handler(trigger)
                except Exception as e:
                    logger.error("notification_failed", channel=channel, error=str(e))

        logger.info(
            "alert_sent",
            condition=trigger.condition_type,
            message=trigger.message,
            severity=trigger.severity,
            channels=channels,
        )
