"""Probability engine — realistic, likelihood-anchored trade ideas.

Why this exists: an LLM idea like "NVDA: wait for a pullback to 210" (while it
trades at 225) is useless without a probability — that dip may never come. This
module turns a price level + time horizon + volatility into an HONEST
probability, and builds a realistic scaled-entry plan so the user is not left
waiting for a fill that never happens.

Deterministic math only (stdlib `math`). Same philosophy as
``ConfidenceCalculator``: the LLM may narrate these numbers but cannot change
them.

Methods (driftless geometric Brownian motion, the neutral/conservative choice —
no assumed direction, which is the honest answer to "how likely is it to dip?"):

* ``touch_probability`` — P(price reaches a level at ANY point within the
  horizon). Reflection principle: ``2 * (1 - Phi(|ln(target/current)| / sigma_T))``
  where ``sigma_T = annual_vol * sqrt(horizon_years)``.
* ``trade_win_probability`` — P(hits take-profit BEFORE stop-loss) via the
  two-barrier gambler's-ruin result in log space: ``|ln(S/stop)| / |ln(tp/stop)|``.
* ``expected_value`` — per-unit EV of reward-vs-risk given that win probability.
* ``realistic_entry_plan`` — the "real solution": P(reach the dream entry), and a
  probability-weighted ladder so you get exposure now AND still catch the dip.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

TRADING_DAYS_PER_YEAR = 252

# Rough per-horizon trading-day spans. Per-stock adaptation (e.g. from the
# Portfolio Manager's time_horizon or volatility) can override these.
HORIZON_DAYS = {
    "INTRADAY": 1,
    "SWING": 15,       # ~3 weeks
    "LONG_TERM": 126,  # ~6 months
}

# Below this probability of reaching a limit entry, "just wait for the dip" is a
# plan that will usually miss — so we switch to a scaled ladder.
LIKELY_ENOUGH = 0.5


def _norm_cdf(x: float) -> float:
    """Standard normal CDF via erf (dependency-free)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def horizon_to_days(horizon: str, default: int = 126) -> int:
    """Map a horizon label (INTRADAY / SWING / LONG_TERM) to trading days."""
    return HORIZON_DAYS.get(str(horizon).upper(), default)


def till_date(horizon_days: int, start: Optional[date] = None) -> date:
    """Per-stock "till when": calendar date the analysis horizon expires.

    Roughly converts trading days to calendar days (x1.4) so the horizon reads
    naturally to a human (e.g. SWING ~3 trading weeks -> ~3 weeks out).
    """
    start = start or date.today()
    return start + timedelta(days=int(round(horizon_days * 1.4)))


def annualized_volatility(closes: list[float], periods: int = TRADING_DAYS_PER_YEAR) -> float:
    """Annualized volatility from a series of closes (log-return stdev)."""
    vals = [float(c) for c in closes if c is not None and float(c) > 0]
    if len(vals) < 2:
        raise ValueError("Need at least 2 closes to compute volatility")
    rets = [math.log(vals[i] / vals[i - 1]) for i in range(1, len(vals))]
    n = len(rets)
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1) if n > 1 else 0.0
    return math.sqrt(var) * math.sqrt(periods)


def _horizon_sigma(annual_vol: float, horizon_days: int) -> float:
    """Std-dev of the log-return over the horizon (driftless)."""
    if annual_vol <= 0:
        raise ValueError("annual_vol must be > 0")
    if horizon_days <= 0:
        raise ValueError("horizon_days must be > 0")
    return annual_vol * math.sqrt(horizon_days / TRADING_DAYS_PER_YEAR)


def touch_probability(current: float, target: float, horizon_days: int, annual_vol: float) -> float:
    """P(price touches `target` at any point within the horizon).

    Works for a target above (upside) or below (a "fallback"/dip) the current
    price. Driftless — the honest, direction-agnostic likelihood. Returns 0..1.
    """
    if current <= 0 or target <= 0:
        raise ValueError("Prices must be > 0")
    sigma_t = _horizon_sigma(annual_vol, horizon_days)
    distance = abs(math.log(target / current))
    m = distance / sigma_t
    return max(0.0, min(1.0, 2.0 * (1.0 - _norm_cdf(m))))


def trade_win_probability(current: float, target: float, stop: float, _annual_vol: float = 0.3) -> float:
    """P(take-profit at `target` is hit BEFORE stop at `stop`).

    `target` and `stop` must straddle `current` (stop below entry, target above
    for a long). Two-barrier gambler's ruin in log space (driftless):
    ``P(target first) = |ln(current/stop)| / |ln(target/stop)|``.
    """
    if current <= 0 or target <= 0 or stop <= 0:
        raise ValueError("Prices must be > 0")
    lo, hi = min(target, stop), max(target, stop)
    if not (lo < current < hi):
        raise ValueError("current must lie strictly between target and stop")
    # Probability of hitting `target` before `stop`.
    return abs(math.log(current / stop)) / abs(math.log(target / stop))


def expected_value(win_prob: float, reward_per_unit: float, risk_per_unit: float) -> float:
    """Per-unit expected value of a trade: p*reward - (1-p)*risk. >0 is +EV."""
    if risk_per_unit < 0 or reward_per_unit < 0:
        raise ValueError("reward/risk must be positive magnitudes")
    return win_prob * reward_per_unit - (1.0 - win_prob) * risk_per_unit


# ---------------------------------------------------------------------------
# Realistic entry plan (the "real solution")
# ---------------------------------------------------------------------------

@dataclass
class LadderRung:
    trigger: str        # e.g. "market now", "on a -2% dip", "limit @ 210"
    fraction: float     # fraction of the intended position to deploy here (0..1)
    note: str = ""


@dataclass
class EntryPlan:
    direction: str
    current: float
    dream_entry: float                 # the LLM's suggested entry level (e.g. 210)
    horizon_days: int
    expires: date
    prob_reach_entry: float            # P(touch dream_entry within horizon)
    likely_to_miss: bool
    ladders: list[LadderRung] = field(default_factory=list)
    expected_entry: Optional[float] = None
    plain_language: str = ""


def realistic_entry_plan(
    current: float,
    dream_entry: float,
    horizon_days: int,
    annual_vol: float,
    direction: str = "long",
    start: Optional[date] = None,
) -> EntryPlan:
    """Build a realistic plan instead of "wait for <level> and hope".

    If the dream entry is genuinely likely (P >= 50%), working a limit there is
    fine. If it is NOT likely, we do not leave the user stranded in cash waiting
    for a fill that may never come — we ladder in now and keep the dream price as
    a bonus rung.
    """
    prob = touch_probability(current, dream_entry, horizon_days, annual_vol)
    likely = prob >= LIKELY_ENOUGH
    expires = till_date(horizon_days, start)

    # A "good" entry for a long is below current (a dip); for a short it is above.
    dip_pct = abs(dream_entry / current - 1.0)

    ladders: list[LadderRung] = []
    if likely:
        # Reasonable to work the limit; split so we don't over-chase one price.
        ladders = [
            LadderRung("market now", 0.5, "get ~half the position on"),
            LadderRung(f"limit @ {dream_entry:.2f}", 0.5, f"{prob:.0%} likely within {horizon_days}d"),
        ]
    else:
        # Dream price is a long shot — do NOT wait for it to fully fill.
        shallow = current * (0.98 if direction == "long" else 1.02)
        ladders = [
            LadderRung("market now", 0.4, "so you don't miss the move"),
            LadderRung(f"on a {(-2 if direction == 'long' else 2)}% dip (~{shallow:.2f})", 0.3, "scale in on weakness"),
            LadderRung(f"limit @ {dream_entry:.2f}", 0.3, f"bonus — only {prob:.0%} likely within {horizon_days}d"),
        ]

    # Probability-weighted expected entry (use reach-prob per rung as a rough weight).
    total = sum(r.fraction for r in ladders) or 1.0
    exp = 0.0
    for r in ladders:
        price = current if r.trigger.startswith("market") else (
            float(r.trigger.split("@")[1].split()[0]) if "@" in r.trigger else (
                current * (0.98 if direction == "long" else 1.02)
            )
        )
        exp += (r.fraction / total) * price

    if likely:
        plain = (
            f"The {dip_pct:.0%} {'dip' if direction == 'long' else 'rip'} to {dream_entry:.2f} is actually likely "
            f"({prob:.0%} within {horizon_days} days, i.e. by {expires.isoformat()}) — "
            f"working a limit here is reasonable. Expected fill ~{exp:.2f}."
        )
    else:
        plain = (
            f"Do NOT just wait for {dream_entry:.2f} — it is only {prob:.0%} likely within {horizon_days} days "
            f"(by {expires.isoformat()}), so you'd probably miss the move. "
            f"Real solution: scale in now (~40% at market, ~30% on a shallow dip) and keep a limit at "
            f"{dream_entry:.2f} for the last ~30% as a bonus. Expected entry ~{exp:.2f}."
        )

    return EntryPlan(
        direction=direction,
        current=current,
        dream_entry=dream_entry,
        horizon_days=horizon_days,
        expires=expires,
        prob_reach_entry=prob,
        likely_to_miss=not likely,
        ladders=ladders,
        expected_entry=exp,
        plain_language=plain,
    )
