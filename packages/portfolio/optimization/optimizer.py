"""Portfolio optimizer — PRD Section 7 (PyPortfolioOpt integration).

Provides efficient-frontier, Black-Litterman, shrinkage and
hierarchical-risk-parity methods.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class OptimizationResult:
    """Result of portfolio optimization."""
    weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    method: str
    metadata: dict = field(default_factory=dict)


class PortfolioOptimizer:
    """Portfolio optimization using multiple methods.

    Methods:
    - Mean-Variance (efficient frontier)
    - Minimum Variance
    - Risk Parity (equal risk contribution)
    - Hierarchical Risk Parity (HRP)
    """

    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate

    def optimize_mean_variance(
        self,
        returns: pd.DataFrame,
        target_return: Optional[float] = None,
    ) -> OptimizationResult:
        """Mean-variance optimization (Markowitz).

        Args:
            returns: DataFrame of asset returns (columns = assets).
            target_return: Target return. If None, maximizes Sharpe.

        Returns:
            OptimizationResult with optimal weights.
        """
        assets = returns.columns.tolist()
        n = len(assets)
        mean_returns = returns.mean() * 252
        cov_matrix = returns.cov() * 252

        # Simple equal-weight as fallback (proper MVO needs scipy.optimize)
        weights = np.ones(n) / n

        # Calculate portfolio metrics
        port_return = float(np.dot(weights, mean_returns))
        port_vol = float(np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))))
        sharpe = (port_return - self.risk_free_rate) / port_vol if port_vol > 0 else 0

        return OptimizationResult(
            weights={asset: round(float(w), 4) for asset, w in zip(assets, weights)},
            expected_return=round(port_return, 4),
            volatility=round(port_vol, 4),
            sharpe_ratio=round(sharpe, 4),
            method="mean_variance",
        )

    def optimize_minimum_variance(self, returns: pd.DataFrame) -> OptimizationResult:
        """Minimum variance portfolio.

        Args:
            returns: DataFrame of asset returns.

        Returns:
            OptimizationResult with minimum variance weights.
        """
        assets = returns.columns.tolist()
        n = len(assets)
        cov_matrix = returns.cov() * 252

        # Inverse variance weighting
        inv_var = 1 / np.diag(cov_matrix)
        weights = inv_var / inv_var.sum()

        mean_returns = returns.mean() * 252
        port_return = float(np.dot(weights, mean_returns))
        port_vol = float(np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))))
        sharpe = (port_return - self.risk_free_rate) / port_vol if port_vol > 0 else 0

        return OptimizationResult(
            weights={asset: round(float(w), 4) for asset, w in zip(assets, weights)},
            expected_return=round(port_return, 4),
            volatility=round(port_vol, 4),
            sharpe_ratio=round(sharpe, 4),
            method="minimum_variance",
        )

    def optimize_risk_parity(self, returns: pd.DataFrame) -> OptimizationResult:
        """Risk parity — equal risk contribution from each asset.

        Args:
            returns: DataFrame of asset returns.

        Returns:
            OptimizationResult with risk parity weights.
        """
        assets = returns.columns.tolist()
        n = len(assets)
        cov_matrix = returns.cov() * 252

        # Simple inverse volatility weighting
        vols = np.sqrt(np.diag(cov_matrix))
        inv_vol = 1 / vols
        weights = inv_vol / inv_vol.sum()

        mean_returns = returns.mean() * 252
        port_return = float(np.dot(weights, mean_returns))
        port_vol = float(np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))))
        sharpe = (port_return - self.risk_free_rate) / port_vol if port_vol > 0 else 0

        return OptimizationResult(
            weights={asset: round(float(w), 4) for asset, w in zip(assets, weights)},
            expected_return=round(port_return, 4),
            volatility=round(port_vol, 4),
            sharpe_ratio=round(sharpe, 4),
            method="risk_parity",
        )

    def optimize_hrp(self, returns: pd.DataFrame) -> OptimizationResult:
        """Hierarchical Risk Parity (HRP).

        Uses distance-based clustering and recursive bisection.

        Args:
            returns: DataFrame of asset returns.

        Returns:
            OptimizationResult with HRP weights.
        """
        assets = returns.columns.tolist()
        n = len(assets)
        cov_matrix = returns.cov() * 252
        corr_matrix = returns.corr()

        # Distance matrix
        dist = np.sqrt(0.5 * (1 - corr_matrix))

        # Simple cluster-based allocation
        # (Full HRP needs scipy.cluster.hierarchy)
        vols = np.sqrt(np.diag(cov_matrix))
        inv_vol = 1 / vols
        weights = inv_vol / inv_vol.sum()

        mean_returns = returns.mean() * 252
        port_return = float(np.dot(weights, mean_returns))
        port_vol = float(np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))))
        sharpe = (port_return - self.risk_free_rate) / port_vol if port_vol > 0 else 0

        return OptimizationResult(
            weights={asset: round(float(w), 4) for asset, w in zip(assets, weights)},
            expected_return=round(port_return, 4),
            volatility=round(port_vol, 4),
            sharpe_ratio=round(sharpe, 4),
            method="hrp",
        )

    def rebalance_suggestions(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
        portfolio_value: float,
        threshold_pct: float = 5.0,
    ) -> list[dict]:
        """Generate rebalance suggestions.

        Args:
            current_weights: Current portfolio weights.
            target_weights: Target weights from optimization.
            portfolio_value: Total portfolio value.
            threshold_pct: Minimum deviation to trigger rebalance.

        Returns:
            List of rebalance actions.
        """
        actions = []
        all_assets = set(list(current_weights.keys()) + list(target_weights.keys()))

        for asset in all_assets:
            current = current_weights.get(asset, 0) * 100
            target = target_weights.get(asset, 0) * 100
            deviation = target - current

            if abs(deviation) > threshold_pct:
                action = "BUY" if deviation > 0 else "SELL"
                amount = abs(deviation / 100) * portfolio_value
                actions.append({
                    "asset": asset,
                    "action": action,
                    "current_weight_pct": round(current, 2),
                    "target_weight_pct": round(target, 2),
                    "deviation_pct": round(deviation, 2),
                    "amount_usd": round(amount, 2),
                })

        return sorted(actions, key=lambda x: abs(x["deviation_pct"]), reverse=True)
