"use client";

import { FlaskConical, Play, BarChart3, TrendingUp, TrendingDown, Clock } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";

/* ── Mock data for layout preview ── */

const DEMO_RUNS = [
  { id: "1", strategy: "SMA Crossover 20/50", horizon: "SWING", status: "COMPLETED", sharpe: 1.42, max_dd: -8.3, win_rate: 58, trades: 127, period: "2022-01 → 2024-12" },
  { id: "2", strategy: "RSI Mean Reversion", horizon: "SWING", status: "COMPLETED", sharpe: 0.89, max_dd: -12.1, win_rate: 52, trades: 89, period: "2022-01 → 2024-12" },
  { id: "3", strategy: "Momentum Breakout", horizon: "LONG_TERM", status: "RUNNING", sharpe: null, max_dd: null, win_rate: null, trades: null, period: "2020-01 → 2024-12" },
];

export default function BacktestsPage() {
  return (
    <div>
      <Header
        title="Backtest Lab"
        subtitle="Run and analyze strategy backtests"
        actions={
          <button className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700">
            <Play className="w-4 h-4" /> New Backtest
          </button>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <Card padding="sm">
          <p className="text-xs text-surface-700 mb-1">Total Runs</p>
          <p className="text-2xl font-bold text-surface-900">3</p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-surface-700 mb-1">Best Sharpe</p>
          <p className="text-2xl font-bold text-success-500">1.42</p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-surface-700 mb-1">Avg Win Rate</p>
          <p className="text-2xl font-bold text-surface-900">55%</p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-surface-700 mb-1">Running</p>
          <p className="text-2xl font-bold text-warning-500">1</p>
        </Card>
      </div>

      {/* Runs table */}
      <Card>
        <CardHeader>
          <CardTitle>Backtest Runs</CardTitle>
        </CardHeader>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-200">
                <th className="text-left py-2 px-3 font-medium text-surface-700">Strategy</th>
                <th className="text-left py-2 px-3 font-medium text-surface-700">Horizon</th>
                <th className="text-left py-2 px-3 font-medium text-surface-700">Period</th>
                <th className="text-left py-2 px-3 font-medium text-surface-700">Status</th>
                <th className="text-right py-2 px-3 font-medium text-surface-700">Sharpe</th>
                <th className="text-right py-2 px-3 font-medium text-surface-700">Max DD</th>
                <th className="text-right py-2 px-3 font-medium text-surface-700">Win Rate</th>
                <th className="text-right py-2 px-3 font-medium text-surface-700">Trades</th>
              </tr>
            </thead>
            <tbody>
              {DEMO_RUNS.map((run) => (
                <tr key={run.id} className="border-b border-surface-100 hover:bg-surface-50">
                  <td className="py-2.5 px-3 font-medium text-surface-900">{run.strategy}</td>
                  <td className="py-2.5 px-3">
                    <span className="px-2 py-0.5 text-xs bg-surface-100 text-surface-700 rounded-full">{run.horizon}</span>
                  </td>
                  <td className="py-2.5 px-3 text-surface-700 font-mono text-xs">{run.period}</td>
                  <td className="py-2.5 px-3">
                    <span className={`px-2 py-0.5 text-xs rounded-full ${
                      run.status === "COMPLETED" ? "bg-green-50 text-success-600" : "bg-amber-50 text-warning-600"
                    }`}>{run.status}</span>
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono">
                    {run.sharpe !== null ? (
                      <span className={run.sharpe > 1 ? "text-success-500 font-medium" : "text-surface-900"}>
                        {run.sharpe.toFixed(2)}
                      </span>
                    ) : "—"}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono text-danger-500">
                    {run.max_dd !== null ? `${run.max_dd}%` : "—"}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono">
                    {run.win_rate !== null ? `${run.win_rate}%` : "—"}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono text-surface-700">
                    {run.trades ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Equity curve placeholder */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Equity Curve — SMA Crossover 20/50</CardTitle>
        </CardHeader>
        <div className="h-64 flex flex-col items-center justify-center text-surface-700 border-2 border-dashed border-surface-200 rounded-lg">
          <BarChart3 className="w-10 h-10 mb-2 text-surface-200" />
          <p className="font-medium">Equity & Drawdown Chart</p>
          <p className="text-sm text-surface-200 mt-1">Connects to backtest results when runs complete</p>
        </div>
      </Card>
    </div>
  );
}
