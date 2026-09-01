"""CSV report generator — PRD Section 1.3.

Generates CSV exports for instruments, portfolios, and signals.
"""

import csv
import io
from datetime import datetime
from typing import Optional


class CSVReportGenerator:
    """Generates CSV reports for the platform."""

    def generate_signals_csv(self, signals: list[dict]) -> str:
        """Generate CSV of active signals."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "Symbol", "State", "Horizon", "Confidence", "Quality Gate",
            "Strategy", "Entry Zone Low", "Entry Zone High",
            "Invalidation Level", "Invalidation Rule",
            "Max Loss %", "Position Size %", "Reason Codes", "Timestamp",
        ])

        for sig in signals:
            writer.writerow([
                sig.get("symbol", ""),
                sig.get("state", ""),
                sig.get("horizon", ""),
                f"{sig.get('confidence', 0):.4f}",
                sig.get("quality_gate", ""),
                sig.get("strategy_name", ""),
                sig.get("entry_zone_low", ""),
                sig.get("entry_zone_high", ""),
                sig.get("invalidation_level", ""),
                sig.get("invalidation_rule", ""),
                sig.get("max_loss_pct", ""),
                sig.get("suggested_size_pct", ""),
                "|".join(sig.get("reason_codes", [])),
                sig.get("created_at", ""),
            ])

        return output.getvalue()

    def generate_portfolio_csv(self, positions: list[dict]) -> str:
        """Generate CSV of portfolio positions."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "Symbol", "Quantity", "Avg Cost", "Current Price",
            "Market Value", "Unrealized P&L", "P&L %", "Weight %",
        ])

        for pos in positions:
            writer.writerow([
                pos.get("symbol", ""),
                f"{pos.get('quantity', 0):.6f}",
                f"{pos.get('avg_cost', 0):.2f}",
                f"{pos.get('current_price', 0):.2f}",
                f"{pos.get('market_value', 0):.2f}",
                f"{pos.get('unrealized_pnl', 0):.2f}",
                f"{pos.get('unrealized_pnl_pct', 0):.2f}",
                f"{pos.get('weight_pct', 0):.2f}",
            ])

        return output.getvalue()

    def generate_backtest_csv(self, trades: list[dict]) -> str:
        """Generate CSV of backtest trades."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "Entry Time", "Exit Time", "Side", "Entry Price", "Exit Price",
            "Quantity", "P&L", "P&L %", "Commission", "Slippage", "Bars Held",
        ])

        for trade in trades:
            writer.writerow([
                trade.get("entry_ts", ""),
                trade.get("exit_ts", ""),
                trade.get("side", ""),
                f"{trade.get('entry_price', 0):.2f}",
                f"{trade.get('exit_price', 0):.2f}",
                f"{trade.get('quantity', 0):.6f}",
                f"{trade.get('pnl', 0):.2f}",
                f"{trade.get('pnl_pct', 0):.2f}",
                f"{trade.get('commission', 0):.2f}",
                f"{trade.get('slippage', 0):.2f}",
                trade.get("bars_held", 0),
            ])

        return output.getvalue()

    def generate_instruments_csv(self, instruments: list[dict]) -> str:
        """Generate CSV of instruments."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "Symbol", "Name", "Type", "Exchange", "Currency", "Status",
            "Sector", "Industry", "ISIN", "CUSIP",
        ])

        for inst in instruments:
            writer.writerow([
                inst.get("symbol", ""),
                inst.get("name", ""),
                inst.get("type", ""),
                inst.get("exchange", ""),
                inst.get("currency", ""),
                inst.get("status", ""),
                inst.get("sector", ""),
                inst.get("industry", ""),
                inst.get("isin", ""),
                inst.get("cusip", ""),
            ])

        return output.getvalue()
