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
  const [showRunForm, setShowRunForm] = useState(false);
  const [runForm, setRunForm] = useState({
    instrument_id: "",
    strategy: "sma_crossover",
    engine: "vectorized",
    timeframe: "1D",
    fast_period: 20,
    slow_period: 50,
    initial_capital: 100000,
    commission_pct: 0.001,
    slippage_pct: 0.0005,
  });
  const [running, setRunning] = useState(false);
  const [walkForward, setWalkForward] = useState<any>(null);

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

  const runBacktest = async () => {
    setRunning(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const endpoint = runForm.engine === "event-driven"
        ? "/api/v1/backtests/event-driven"
        : "/api/v1/backtests/run";
      const res = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(runForm),
      });
      if (res.ok) {
        const data = await res.json();
        setRuns((prev) => [data, ...prev]);
        setSelectedRun(data);
        setShowRunForm(false);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setRunning(false);
    }
  };

  const runWalkForward = async () => {
    setRunning(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const res = await fetch("/api/v1/backtests/walk-forward", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          instrument_id: runForm.instrument_id,
          strategy: runForm.strategy,
          timeframe: runForm.timeframe,
          fast_period: runForm.fast_period,
          slow_period: runForm.slow_period,
          n_splits: 5,
          initial_capital: runForm.initial_capital,
          commission_pct: runForm.commission_pct,
          slippage_pct: runForm.slippage_pct,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setWalkForward(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setRunning(false);
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
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowRunForm(!showRunForm)}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700"
            >
              <Play className="w-4 h-4" />
              Run Backtest
            </button>
          </div>
        }
      />

      {/* Run Form */}
      {showRunForm && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Run Backtest</CardTitle>
          </CardHeader>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-medium text-surface-700 mb-1">Instrument ID</label>
              <input
                type="text"
                value={runForm.instrument_id}
                onChange={(e) => setRunForm((f) => ({ ...f, instrument_id: e.target.value }))}
                className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2"
                placeholder="UUID"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-700 mb-1">Strategy</label>
              <select
                value={runForm.strategy}
                onChange={(e) => setRunForm((f) => ({ ...f, strategy: e.target.value }))}
                className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2"
              >
                <option value="sma_crossover">SMA Crossover</option>
                <option value="rsi_reversion">RSI Reversion</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-700 mb-1">Engine</label>
              <select
                value={runForm.engine}
                onChange={(e) => setRunForm((f) => ({ ...f, engine: e.target.value }))}
                className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2"
              >
                <option value="vectorized">Vectorized</option>
                <option value="event-driven">Event-Driven</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-700 mb-1">Timeframe</label>
              <select
                value={runForm.timeframe}
                onChange={(e) => setRunForm((f) => ({ ...f, timeframe: e.target.value }))}
                className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2"
              >
                <option value="1D">Daily</option>
                <option value="1H">Hourly</option>
                <option value="15m">15 min</option>
                <option value="5m">5 min</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-700 mb-1">Fast Period</label>
              <input
                type="number"
                value={runForm.fast_period}
                onChange={(e) => setRunForm((f) => ({ ...f, fast_period: Number(e.target.value) }))}
                className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-700 mb-1">Slow Period</label>
              <input
                type="number"
                value={runForm.slow_period}
                onChange={(e) => setRunForm((f) => ({ ...f, slow_period: Number(e.target.value) }))}
                className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-700 mb-1">Commission %</label>
              <input
                type="number"
                step="0.0001"
                value={runForm.commission_pct}
                onChange={(e) => setRunForm((f) => ({ ...f, commission_pct: Number(e.target.value) }))}
                className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-700 mb-1">Slippage %</label>
              <input
                type="number"
                step="0.0001"
                value={runForm.slippage_pct}
                onChange={(e) => setRunForm((f) => ({ ...f, slippage_pct: Number(e.target.value) }))}
                className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2"
              />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button
              onClick={runBacktest}
              disabled={running || !runForm.instrument_id}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              Run
            </button>
            <button
              onClick={runWalkForward}
              disabled={running || !runForm.instrument_id}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-primary-600 border border-primary-200 rounded-lg hover:bg-primary-50 disabled:opacity-50"
            >
              {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <FlaskConical className="w-4 h-4" />}
              Walk-Forward
            </button>
          </div>
        </Card>
      )}

      {/* Walk-Forward Results */}
      {walkForward && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Walk-Forward Validation</CardTitle>
          </CardHeader>
          <div className="grid grid-cols-4 gap-4 mb-4">
            <div>
              <p className="text-xs text-surface-700">Avg Return</p>
              <p className="text-lg font-bold">{format.pct(walkForward.avg_return)}</p>
            </div>
            <div>
              <p className="text-xs text-surface-700">Avg Sharpe</p>
              <p className="text-lg font-bold">{walkForward.avg_sharpe.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-xs text-surface-700">Avg Max DD</p>
              <p className="text-lg font-bold text-danger-500">{walkForward.avg_max_drawdown.toFixed(2)}%</p>
            </div>
            <div>
              <p className="text-xs text-surface-700">Consistency</p>
              <p className="text-lg font-bold">{(walkForward.consistency * 100).toFixed(0)}%</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-surface-300">
                  <th className="text-left py-1 px-2">Split</th>
                  <th className="text-right py-1 px-2">Return</th>
                  <th className="text-right py-1 px-2">Sharpe</th>
                  <th className="text-right py-1 px-2">Max DD</th>
                  <th className="text-right py-1 px-2">Win Rate</th>
                  <th className="text-right py-1 px-2">Trades</th>
                </tr>
              </thead>
              <tbody>
                {walkForward.splits.map((s: any, i: number) => (
                  <tr key={i} className="border-b border-surface-200">
                    <td className="py-1 px-2">{i + 1}</td>
                    <td className={`py-1 px-2 text-right font-mono ${format.changeColor(s.total_return)}`}>{format.pct(s.total_return)}</td>
                    <td className="py-1 px-2 text-right font-mono">{s.sharpe_ratio.toFixed(2)}</td>
                    <td className="py-1 px-2 text-right font-mono text-danger-500">{s.max_drawdown.toFixed(2)}%</td>
                    <td className="py-1 px-2 text-right font-mono">{s.win_rate.toFixed(1)}%</td>
                    <td className="py-1 px-2 text-right font-mono">{s.total_trades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

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
              <FlaskConical className="w-10 h-10 mb-2 text-surface-400" />
              <p className="font-medium">No backtests yet</p>
              <p className="text-sm text-surface-400 mt-1">Run a backtest from the API</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-300">
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
                      className={`border-b border-surface-200 cursor-pointer transition-colors ${
                        selectedRun?.id === run.id ? "bg-primary-50" : "hover:bg-surface-200"
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
