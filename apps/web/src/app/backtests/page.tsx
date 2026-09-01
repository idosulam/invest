"use client";

import { useState, useEffect } from "react";
import {
  FlaskConical,
  Play,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
} from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";
import { format } from "@/lib/format";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  ComposedChart,
} from "recharts";

/* ── Types ── */

interface BacktestMetrics {
  total_return: number;
  annualized_return: number;
  volatility: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  calmar_ratio: number;
  win_rate: number;
  payoff_ratio: number;
  total_trades: number;
  avg_trade_duration_days: number;
  total_costs: number;
}

interface BacktestRun {
  id: string;
  instrument_id: string;
  symbol: string | null;
  strategy_name: string;
  status: string;
  metrics: BacktestMetrics | null;
  equity_curve: number[];
  drawdown_curve: number[];
  timestamps: string[];
  trades_count: number;
  config: Record<string, any>;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

/* ── Page ── */

export default function BacktestsPage() {
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedRun, setSelectedRun] = useState<BacktestRun | null>(null);

  useEffect(() => {
    fetchRuns();
  }, []);

  const fetchRuns = async () => {
    setLoading(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const res = await fetch("/api/v1/backtests?limit=50", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setRuns(data.items);
        if (data.items.length > 0 && !selectedRun) {
          setSelectedRun(data.items[0]);
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const bestSharpe = runs.reduce((best, r) => {
    const s = r.metrics?.sharpe_ratio ?? 0;
    return s > best ? s : best;
  }, 0);

  const avgWinRate = runs.filter((r) => r.metrics).length > 0
    ? runs.reduce((sum, r) => sum + (r.metrics?.win_rate ?? 0), 0) / runs.filter((r) => r.metrics).length
    : 0;

  const runningCount = runs.filter((r) => r.status === "RUNNING").length;

  return (
    <div>
      <Header
        title="Backtest Lab"
        subtitle="Run and analyze strategy backtests"
      />

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <Card padding="sm">
          <p className="text-xs text-surface-700 mb-1">Total Runs</p>
          <p className="text-2xl font-bold text-surface-900">{runs.length}</p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-surface-700 mb-1">Best Sharpe</p>
          <p className="text-2xl font-bold text-success-500">{bestSharpe.toFixed(2)}</p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-surface-700 mb-1">Avg Win Rate</p>
          <p className="text-2xl font-bold text-surface-900">{avgWinRate.toFixed(1)}%</p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-surface-700 mb-1">Running</p>
          <p className="text-2xl font-bold text-warning-500">{runningCount}</p>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Runs table */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Backtest Runs</CardTitle>
          </CardHeader>

          {loading ? (
            <div className="h-48 flex items-center justify-center text-surface-700">
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading...
            </div>
          ) : runs.length === 0 ? (
            <div className="h-48 flex flex-col items-center justify-center text-surface-700">
              <FlaskConical className="w-10 h-10 mb-2 text-surface-200" />
              <p className="font-medium">No backtests yet</p>
              <p className="text-sm text-surface-200 mt-1">Run a backtest from the API</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-200">
                    <th className="text-left py-2 px-3 font-medium text-surface-700">Strategy</th>
                    <th className="text-left py-2 px-3 font-medium text-surface-700">Symbol</th>
                    <th className="text-left py-2 px-3 font-medium text-surface-700">Status</th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700">Return</th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700">Sharpe</th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700">Max DD</th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700">Win Rate</th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700">Trades</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr
                      key={run.id}
                      onClick={() => setSelectedRun(run)}
                      className={`border-b border-surface-100 cursor-pointer transition-colors ${
                        selectedRun?.id === run.id ? "bg-primary-50" : "hover:bg-surface-50"
                      }`}
                    >
                      <td className="py-2.5 px-3 font-medium text-surface-900">{run.strategy_name}</td>
                      <td className="py-2.5 px-3 text-surface-700">{run.symbol ?? "—"}</td>
                      <td className="py-2.5 px-3">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full ${
                          run.status === "COMPLETED" ? "bg-green-50 text-success-600"
                            : run.status === "FAILED" ? "bg-red-50 text-danger-600"
                            : "bg-amber-50 text-warning-600"
                        }`}>
                          {run.status === "COMPLETED" ? <CheckCircle className="w-3 h-3" />
                            : run.status === "FAILED" ? <XCircle className="w-3 h-3" />
                            : <Loader2 className="w-3 h-3 animate-spin" />}
                          {run.status}
                        </span>
                      </td>
                      <td className={`py-2.5 px-3 text-right font-mono ${format.changeColor(run.metrics?.total_return ?? 0)}`}>
                        {run.metrics ? format.pct(run.metrics.total_return) : "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono">
                        {run.metrics?.sharpe_ratio?.toFixed(2) ?? "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-danger-500">
                        {run.metrics ? `${run.metrics.max_drawdown}%` : "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono">
                        {run.metrics ? `${run.metrics.win_rate}%` : "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-surface-700">
                        {run.metrics?.total_trades ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Detail panel */}
        <div className="space-y-4">
          {selectedRun?.metrics && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Metrics</CardTitle>
                </CardHeader>
                <div className="space-y-2 text-sm">
                  {[
                    ["Total Return", format.pct(selectedRun.metrics.total_return)],
                    ["Annualized", format.pct(selectedRun.metrics.annualized_return)],
                    ["Volatility", `${selectedRun.metrics.volatility}%`],
                    ["Sharpe", selectedRun.metrics.sharpe_ratio.toFixed(2)],
                    ["Sortino", selectedRun.metrics.sortino_ratio.toFixed(2)],
                    ["Max Drawdown", `${selectedRun.metrics.max_drawdown}%`],
                    ["Calmar", selectedRun.metrics.calmar_ratio.toFixed(2)],
                    ["Win Rate", `${selectedRun.metrics.win_rate}%`],
                    ["Payoff", selectedRun.metrics.payoff_ratio.toFixed(2)],
                    ["Trades", String(selectedRun.metrics.total_trades)],
                    ["Avg Duration", `${selectedRun.metrics.avg_trade_duration_days}d`],
                    ["Total Costs", format.currency(selectedRun.metrics.total_costs)],
                  ].map(([label, value]) => (
                    <div key={label} className="flex justify-between">
                      <span className="text-surface-700">{label}</span>
                      <span className="font-mono text-surface-900">{value}</span>
                    </div>
                  ))}
                </div>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Config</CardTitle>
                </CardHeader>
                <div className="space-y-1.5 text-xs font-mono">
                  {Object.entries(selectedRun.config).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-surface-700">{k}</span>
                      <span className="text-surface-900">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </Card>
            </>
          )}

          {selectedRun?.error && (
            <Card>
              <div className="flex items-start gap-2">
                <XCircle className="w-5 h-5 text-danger-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-surface-900">Error</p>
                  <p className="text-sm text-surface-700 mt-1">{selectedRun.error}</p>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* Equity curve */}
      {selectedRun?.equity_curve && selectedRun.equity_curve.length > 0 && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Equity Curve — {selectedRun.strategy_name}</CardTitle>
          </CardHeader>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart
              data={selectedRun.equity_curve.map((v, i) => ({
                equity: v,
                drawdown: selectedRun.drawdown_curve[i] ?? 0,
              }))}
              margin={{ top: 5, right: 5, left: 5, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <YAxis tick={{ fontSize: 11, fill: "#64748b" }} stroke="#cbd5e1" width={70} />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="equity"
                fill="#dbeafe"
                stroke="#3b82f6"
                strokeWidth={2}
                name="Equity"
              />
            </ComposedChart>
          </ResponsiveContainer>

          {/* Drawdown chart */}
          <p className="text-xs font-medium text-surface-700 mt-4 mb-2">DRAWDOWN</p>
          <ResponsiveContainer width="100%" height={100}>
            <ComposedChart
              data={selectedRun.drawdown_curve.map((v) => ({ drawdown: v }))}
              margin={{ top: 0, right: 5, left: 5, bottom: 5 }}
            >
              <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} stroke="#e2e8f0" width={70} />
              <Area
                type="monotone"
                dataKey="drawdown"
                fill="#fef2f2"
                stroke="#ef4444"
                strokeWidth={1}
                name="Drawdown %"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}
