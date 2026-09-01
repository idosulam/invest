"""Performance attribution — PRD Section 1.3.

Decomposes portfolio returns into sector, factor, and position contributions.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class AttributionEntry:
    """Single attribution entry."""
    name: str  # sector, factor, or position
    weight: float  # portfolio weight
    return_contribution: float  # contribution to total return
    excess_return: float  # vs benchmark
    metadata: dict = field(default_factory=dict)


@dataclass
class AttributionResult:
    """Full attribution breakdown."""
    total_return: float
    benchmark_return: float
    active_return: float
    entries: list[AttributionEntry]
    method: str


class PerformanceAttribution:
    """Performance attribution engine.

    Methods:
    - Brinson attribution (allocation + selection + interaction)
    - Sector attribution
    - Position-level attribution
    """

    def brinson_attribution(
        self,
        portfolio_weights: dict[str, float],
        benchmark_weights: dict[str, float],
        portfolio_returns: dict[str, float],
        benchmark_returns: dict[str, float],
    ) -> AttributionResult:
        """Brinson-Fachler attribution.

        Decomposes active return into:
        - Allocation effect: overweight/underweight sectors
        - Selection effect: stock picking within sectors
        - Interaction effect: combined impact

        Args:
            portfolio_weights: Portfolio weights by sector/asset.
            benchmark_weights: Benchmark weights by sector/asset.
            portfolio_returns: Portfolio returns by sector/asset.
            benchmark_returns: Benchmark returns by sector/asset.

        Returns:
            AttributionResult with allocation, selection, interaction.
        """
        all_keys = set(list(portfolio_weights.keys()) + list(benchmark_weights.keys()))

        total_port_return = sum(
            portfolio_weights.get(k, 0) * portfolio_returns.get(k, 0)
            for k in all_keys
        )
        total_bench_return = sum(
            benchmark_weights.get(k, 0) * benchmark_returns.get(k, 0)
            for k in all_keys
        )

        entries = []
        for key in all_keys:
            wp = portfolio_weights.get(key, 0)
            wb = benchmark_weights.get(key, 0)
            rp = portfolio_returns.get(key, 0)
            rb = benchmark_returns.get(key, 0)

            # Allocation: (wp - wb) * (rb - total_bench)
            allocation = (wp - wb) * (rb - total_bench_return)

            # Selection: wb * (rp - rb)
            selection = wb * (rp - rb)

            # Interaction: (wp - wb) * (rp - rb)
            interaction = (wp - wb) * (rp - rb)

            total_contribution = allocation + selection + interaction

            entries.append(AttributionEntry(
                name=key,
                weight=wp,
                return_contribution=round(wp * rp, 6),
                excess_return=round(total_contribution, 6),
                metadata={
                    "allocation": round(allocation, 6),
                    "selection": round(selection, 6),
                    "interaction": round(interaction, 6),
                },
            ))

        return AttributionResult(
            total_return=round(total_port_return, 6),
            benchmark_return=round(total_bench_return, 6),
            active_return=round(total_port_return - total_bench_return, 6),
            entries=sorted(entries, key=lambda e: abs(e.excess_return), reverse=True),
            method="brinson_fachler",
        )

    def sector_attribution(
        self,
        positions: list[dict],
        sector_map: dict[str, str],
    ) -> AttributionResult:
        """Sector-level attribution.

        Args:
            positions: List of dicts with instrument_id, weight, return.
            sector_map: Mapping of instrument_id to sector.

        Returns:
            AttributionResult by sector.
        """
        sector_weights: dict[str, float] = {}
        sector_returns: dict[str, float] = {}

        for pos in positions:
            inst_id = pos["instrument_id"]
            sector = sector_map.get(inst_id, "Unknown")
            weight = pos.get("weight", 0)
            ret = pos.get("return", 0)

            if sector not in sector_weights:
                sector_weights[sector] = 0
                sector_returns[sector] = 0

            sector_weights[sector] += weight
            # Weighted return contribution
            sector_returns[sector] = (
                (sector_returns[sector] * (sector_weights[sector] - weight) + ret * weight)
                / sector_weights[sector]
                if sector_weights[sector] > 0 else 0
            )

        total_return = sum(w * r for w, r in zip(sector_weights.values(), sector_returns.values()))

        entries = []
        for sector in sector_weights:
            w = sector_weights[sector]
            r = sector_returns[sector]
            entries.append(AttributionEntry(
                name=sector,
                weight=w,
                return_contribution=round(w * r, 6),
                excess_return=round(w * r, 6),
            ))

        return AttributionResult(
            total_return=round(total_return, 6),
            benchmark_return=0,
            active_return=round(total_return, 6),
            entries=sorted(entries, key=lambda e: e.return_contribution, reverse=True),
            method="sector",
        )

    def position_attribution(
        self,
        positions: list[dict],
    ) -> AttributionResult:
        """Position-level attribution.

        Args:
            positions: List of dicts with symbol, weight, return.

        Returns:
            AttributionResult by position.
        """
        total_return = sum(p.get("weight", 0) * p.get("return", 0) for p in positions)

        entries = []
        for pos in positions:
            w = pos.get("weight", 0)
            r = pos.get("return", 0)
            entries.append(AttributionEntry(
                name=pos.get("symbol", "Unknown"),
                weight=w,
                return_contribution=round(w * r, 6),
                excess_return=round(w * r, 6),
            ))

        return AttributionResult(
            total_return=round(total_return, 6),
            benchmark_return=0,
            active_return=round(total_return, 6),
            entries=sorted(entries, key=lambda e: e.return_contribution, reverse=True),
            method="position",
        )
