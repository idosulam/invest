"""HTML report generator — PRD Section 1.3.

Generates styled HTML reports for instruments, portfolios, and signals.
"""

from datetime import datetime
from typing import Optional


class HTMLReportGenerator:
    """Generates HTML reports for the platform."""

    def generate_instrument_report(
        self,
        symbol: str,
        name: str,
        bars: list[dict],
        signals: list[dict],
        fundamentals: dict,
    ) -> str:
        """Generate instrument analysis report."""
        latest_price = bars[-1]["close"] if bars else 0
        price_change = ((bars[-1]["close"] / bars[-2]["close"] - 1) * 100) if len(bars) >= 2 else 0

        signals_html = ""
        for sig in signals[:10]:
            signals_html += f"""
            <tr>
                <td>{sig.get('state', '—')}</td>
                <td>{sig.get('horizon', '—')}</td>
                <td>{sig.get('confidence', 0):.0%}</td>
                <td>{sig.get('quality_gate', '—')}</td>
                <td>{sig.get('strategy_name', '—')}</td>
            </tr>"""

        fundamentals_html = ""
        for key, value in fundamentals.items():
            fundamentals_html += f"<tr><td>{key}</td><td>{value}</td></tr>"

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{symbol} — Market Analysis Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 40px; color: #1a1a1a; }}
        .header {{ border-bottom: 2px solid #2563eb; padding-bottom: 20px; margin-bottom: 30px; }}
        .price {{ font-size: 32px; font-weight: bold; }}
        .positive {{ color: #16a34a; }}
        .negative {{ color: #dc2626; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #e5e7eb; padding: 10px; text-align: left; }}
        th {{ background: #f9fafb; font-weight: 600; }}
        .section {{ margin: 30px 0; }}
        .disclaimer {{ margin-top: 40px; padding: 15px; background: #fef3c7; border-radius: 8px; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{symbol} — {name}</h1>
        <div class="price {'positive' if price_change >= 0 else 'negative'}">
            ${latest_price:,.2f} ({price_change:+.2f}%)
        </div>
        <p>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
    </div>

    <div class="section">
        <h2>Active Signals</h2>
        <table>
            <tr><th>State</th><th>Horizon</th><th>Confidence</th><th>Quality</th><th>Strategy</th></tr>
            {signals_html if signals_html else '<tr><td colspan="5">No active signals</td></tr>'}
        </table>
    </div>

    <div class="section">
        <h2>Fundamentals</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            {fundamentals_html if fundamentals_html else '<tr><td colspan="2">No fundamental data</td></tr>'}
        </table>
    </div>

    <div class="disclaimer">
        ⚠️ This report is for research and decision-support purposes only.
        Not financial advice. Past performance does not guarantee future results.
        Paper trading only — no live orders.
    </div>
</body>
</html>"""

    def generate_portfolio_report(
        self,
        portfolio_name: str,
        positions: list[dict],
        total_value: float,
        total_pnl: float,
        allocation: dict,
    ) -> str:
        """Generate portfolio report."""
        positions_html = ""
        for pos in positions:
            pnl_class = "positive" if pos.get("unrealized_pnl", 0) >= 0 else "negative"
            positions_html += f"""
            <tr>
                <td>{pos.get('symbol', '—')}</td>
                <td>{pos.get('quantity', 0):,.2f}</td>
                <td>${pos.get('avg_cost', 0):,.2f}</td>
                <td>${pos.get('current_price', 0):,.2f}</td>
                <td class="{pnl_class}">${pos.get('unrealized_pnl', 0):,.2f}</td>
                <td class="{pnl_class}">{pos.get('unrealized_pnl_pct', 0):+.2f}%</td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{portfolio_name} — Portfolio Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 40px; }}
        .positive {{ color: #16a34a; }}
        .negative {{ color: #dc2626; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #e5e7eb; padding: 10px; text-align: left; }}
        th {{ background: #f9fafb; }}
        .summary {{ display: flex; gap: 30px; margin: 20px 0; }}
        .metric {{ padding: 15px; background: #f9fafb; border-radius: 8px; }}
        .disclaimer {{ margin-top: 40px; padding: 15px; background: #fef3c7; border-radius: 8px; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>{portfolio_name}</h1>
    <p>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>

    <div class="summary">
        <div class="metric">
            <div>Total Value</div>
            <div style="font-size: 24px; font-weight: bold;">${total_value:,.2f}</div>
        </div>
        <div class="metric">
            <div>Total P&L</div>
            <div style="font-size: 24px; font-weight: bold;" class="{'positive' if total_pnl >= 0 else 'negative'}">
                ${total_pnl:,.2f}
            </div>
        </div>
    </div>

    <h2>Positions</h2>
    <table>
        <tr><th>Symbol</th><th>Quantity</th><th>Avg Cost</th><th>Current</th><th>P&L</th><th>P&L %</th></tr>
        {positions_html if positions_html else '<tr><td colspan="6">No positions</td></tr>'}
    </table>

    <div class="disclaimer">
        ⚠️ Paper portfolio only. Not financial advice.
    </div>
</body>
</html>"""

    def generate_signal_report(self, signals: list[dict]) -> str:
        """Generate signals summary report."""
        rows = ""
        for sig in signals:
            rows += f"""
            <tr>
                <td>{sig.get('symbol', '—')}</td>
                <td>{sig.get('state', '—')}</td>
                <td>{sig.get('horizon', '—')}</td>
                <td>{sig.get('confidence', 0):.0%}</td>
                <td>{sig.get('quality_gate', '—')}</td>
                <td>{sig.get('strategy_name', '—')}</td>
                <td>{', '.join(sig.get('reason_codes', []))}</td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Signals Report</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 40px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #e5e7eb; padding: 8px; text-align: left; }}
        th {{ background: #f9fafb; }}
    </style>
</head>
<body>
    <h1>Active Signals Report</h1>
    <p>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
    <table>
        <tr><th>Symbol</th><th>State</th><th>Horizon</th><th>Confidence</th><th>Quality</th><th>Strategy</th><th>Reasons</th></tr>
        {rows if rows else '<tr><td colspan="7">No signals</td></tr>'}
    </table>
    <p style="margin-top:30px;font-size:12px;color:#666;">⚠️ Research only. Not financial advice.</p>
</body>
</html>"""
