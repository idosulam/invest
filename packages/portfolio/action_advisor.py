"""Portfolio-aware action mapper — signals personalized to YOUR book.

Turns a model signal + your actual position into a concrete decision:
INITIATE / ADD / TRIM(part) / HOLD / EXIT / WATCH — and how much to trade.
Anchored to your entry (cost basis), so e.g. a winner is trimmed into strength
while a broken-thesis loser respects the stop.

Deterministic decision table (no LLM). The LLM supplies the signal; this module
decides what that signal means for THIS holding given qty, avg_cost, weight.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Action(str, Enum):
    INITIATE = "INITIATE"   # no position -> open (scaled)
    ADD = "ADD"             # top up an existing position (buy part)
    TRIM = "TRIM"           # sell PART of the position (de-risk / take profit)
    EXIT = "EXIT"           # sell the whole position
    HOLD = "HOLD"           # do nothing, thesis intact
    WATCH = "WATCH"         # no position yet, wait for trigger
    AVOID = "AVOID"         # do not open (signal is bearish)


@dataclass
class PositionContext:
    current_price: float
    portfolio_value: float
    quantity: float = 0.0                 # 0 => no position
    avg_cost: float = 0.0                # entry / cost basis per share
    target_weight: float = 0.05          # intended weight of this name (e.g. 5%)

    @property
    def has_position(self) -> bool:
        return self.quantity > 0

    @property
    def position_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def weight(self) -> float:
        return self.position_value / self.portfolio_value if self.portfolio_value > 0 else 0.0

    @property
    def pnl_pct(self) -> float:
        """Unrealized return vs entry (cost basis). 0 if no position."""
        if not self.has_position or self.avg_cost <= 0:
            return 0.0
        return self.current_price / self.avg_cost - 1.0


@dataclass
class AdvisorDecision:
    action: Action
    trade_shares: float                  # signed: +buy / -sell (0 for HOLD/WATCH)
    trade_value: float                   # signed $
    trade_pct_of_position: float         # fraction of current position traded (0 if none/new)
    new_weight: float                    # projected weight after the trade
    pnl_pct: float                       # return vs entry driving the call
    rationale: str


def recommend(
    signal_state: str,
    ctx: PositionContext,
    *,
    trim_fraction: float = 0.4,
    add_fraction: float = 0.5,
    initiate_fraction: float = 0.5,
    stop_price: Optional[float] = None,
) -> AdvisorDecision:
    """Map (signal_state, position) -> concrete, sized action.

    signal_state: ENTER_LONG / HOLD / REDUCE / EXIT / WATCH (see SignalState).
    Sizes are fractions of the position/target, deliberately conservative —
    scale in and out rather than all-or-nothing.
    """
    state = str(signal_state).upper()
    pnl = ctx.pnl_pct
    w = ctx.weight
    tw = ctx.target_weight

    def _decision(action, shares=0.0, value=0.0, pct_pos=0.0, why=""):
        new_val = ctx.position_value + value
        new_w = new_val / ctx.portfolio_value if ctx.portfolio_value > 0 else 0.0
        return AdvisorDecision(
            action=action,
            trade_shares=round(shares, 6),
            trade_value=round(value, 2),
            trade_pct_of_position=round(pct_pos, 4),
            new_weight=round(new_w, 4),
            pnl_pct=round(pnl, 4),
            rationale=why,
        )

    def _buy(dollars, why, pct_pos=0.0):
        shares = dollars / ctx.current_price if ctx.current_price > 0 else 0.0
        return _decision(Action.ADD if ctx.has_position else Action.INITIATE,
                         shares=shares, value=dollars, pct_pos=pct_pos, why=why)

    def _sell(frac_of_position, why):
        value = ctx.position_value * frac_of_position
        shares = (ctx.quantity * frac_of_position) if ctx.has_position else 0.0
        act = Action.EXIT if frac_of_position >= 0.999 else Action.TRIM
        return _decision(act, shares=-shares, value=-value, pct_pos=frac_of_position, why=why)

    # ── No position yet ────────────────────────────────────────────────────
    if not ctx.has_position:
        if state in ("ENTER_LONG", "BUY"):
            dollars = ctx.portfolio_value * tw * initiate_fraction
            return _buy(dollars,
                        why=f"Initiate a starter position (~{initiate_fraction:.0%} of your {tw:.0%} target) — "
                            f"signal is bullish and you have no exposure yet; scale rather than jump all-in.",
                        pct_pos=0.0)
        if state in ("REDUCE", "EXIT", "SELL"):
            return _decision(Action.AVOID,
                             why="Signal is bearish/exit and you hold nothing — stay out.")
        # HOLD / WATCH
        return _decision(Action.WATCH,
                         why="No position and no entry trigger yet — watch for the setup; "
                             "see the entry plan for a realistic way in.")

    # ── Has a position — decide off signal + entry (cost basis) + weight ────
    stop_hit = stop_price is not None and ctx.current_price <= stop_price

    if state in ("EXIT", "SELL") or stop_hit:
        why = ("Thesis broken / exit signal — close the whole position"
               + (" (stop level hit)." if stop_hit else ".")
               + f" You are {pnl:+.0%} vs entry {ctx.avg_cost:.2f}.")
        return _sell(1.0, why)

    if state in ("REDUCE",):
        return _sell(trim_fraction,
                     why=f"Reduce signal — trim ~{trim_fraction:.0%} of the position to de-risk. "
                         f"You are {pnl:+.0%} vs entry {ctx.avg_cost:.2f}."
                         + (" Take some profit into strength." if pnl > 0 else " Cut exposure while you manage the rest."))

    if state in ("ENTER_LONG", "BUY"):
        if w >= tw * 1.1:  # already at/over target weight
            if pnl > 0.05:  # nice winner + concentrated -> trim into strength
                return _sell(trim_fraction,
                             why=f"Bullish, but you are already {w:.0%} (target {tw:.0%}) and up {pnl:+.0%} — "
                                 f"trim ~{trim_fraction:.0%} into strength to stay diversified; let the rest run.")
            return _decision(Action.HOLD,
                             why=f"Bullish thesis intact, but position is already {w:.0%} (target {tw:.0%}) — "
                                 f"{pnl:+.0%} vs entry. Hold; don't over-concentrate.")
        gap_dollars = ctx.portfolio_value * (tw - w) * add_fraction
        return _buy(gap_dollars,
                    why=f"Bullish and underweight ({w:.0%} vs {tw:.0%} target) — add ~{add_fraction:.0%} of the gap. "
                        f"You are {pnl:+.0%} vs entry {ctx.avg_cost:.2f}; adding here improves your basis.",
                    pct_pos=0.0)

    # HOLD / WATCH with a position
    if w > tw * 1.3:  # badly over-concentrated -> rebalance down
        return _sell(trim_fraction,
                     why=f"Hold thesis, but position is {w:.0%} vs {tw:.0%} target (over-concentrated) — "
                         f"trim ~{trim_fraction:.0%} back toward target. {pnl:+.0%} vs entry.")
    if pnl < -0.15:  # deep loser without a hold thesis
        return _decision(Action.HOLD,
                         why=f"Down {pnl:+.0%} vs entry {ctx.avg_cost:.2f}, but no exit signal — hold and monitor; "
                             f"respect your stop rather than panic-selling. Avoid adding to a loser here.")
    return _decision(Action.HOLD,
                     why=f"Hold — thesis intact. {pnl:+.0%} vs entry {ctx.avg_cost:.2f}, "
                         f"weight {w:.0%} of a {tw:.0%} target.")
