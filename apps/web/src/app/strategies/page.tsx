"use client";

import { useState, useEffect } from "react";
import { strategies as strategiesApi, strategyPerformance } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";
import { format } from "@/lib/format";
import {
  Target,
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart3,
  AlertTriangle,
  Loader2,
  ChevronDown,
  ChevronUp,
  Clock,
  Zap,
} from "lucide-react";

/* ── Types ── */

interface StrategyCard {
  name: string;
  version: string;
  horizon: string;
  description: string;
  tags: string[];
  required_lookback: number;
}

interface PerformanceData {
  strategy_name: string;
  instrument_id: string;
  symbol: string;
  total_return: number | null;
  annualized_return: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown: number | null;
  win_rate: number | null;
  payoff_ratio: number | null;
  total_trades: number | null;
  total_costs: number | null;
  data_caveat: string | null;
  run_at: string;
}

/* ── Horizon styling ── */

const HORIZON_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  LONG_TERM: { color: "text-purple-700", bg: "bg-purple-50", label: "Long Term" },
  SWING: { color: "text-blue-700", bg: "bg-blue-50", label: "Swing" },
  INTRADAY: { color: "text-amber-700", bg: "bg-amber-50", label: "Intraday" },
};

/* ── Strategy Card Component ── */

function StrategyCardView({
  strategy,
  performances,
}: {
  strategy: StrategyCard;
  performances: PerformanceData[];
}) {
  const [expanded, setExpanded] = useState(false);
  const horizonCfg = HORIZON_CONFIG[strategy.horizon] || HORIZON_CONFIG.SWING;

  // Aggregate stats across all instruments
  const validPerfs = performances.filter((p) => p.total_trades && p.total_trades > 0);
  const avgWinRate =
    validPerfs.length > 0
      ? validPerfs.reduce((sum, p) => sum + (p.win_rate ?? 0), 0) / validPerfs.length
      : null;
  const avgReturn =
    validPerfs.length > 0
      ? validPerfs.reduce((sum, p) => sum + (p.total_return ?? 0), 0) / validPerfs.length
      : null;
  const avgSharpe =
    validPerfs.length > 0
      ? validPerfs.reduce((sum, p) => sum + (p.sharpe_ratio ?? 0), 0) / validPerfs.length
      : null;
  const totalTrades = validPerfs.reduce((sum, p) => sum + (p.total_trades ?? 0), 0);
  const hasCaveat = performances.some((p) => p.data_caveat);

  return (
    <Card className="overflow-hidden">
      <div
        className="flex items-start justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start gap-3">
          <div className={`p-2.5 rounded-lg ${horizonCfg.bg}`}>
            <Target className={`w-5 h-5 ${horizonCfg.color}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold text-surface-900">{strategy.name}</h3>
              <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${horizonCfg.bg} ${horizonCfg.color}`}>
                {horizonCfg.label}
              </span>
              {hasCaveat && (
                <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-amber-50 text-amber-700 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  Daily bars only
                </span>
              )}
            </div>
            <p className="text-sm text-surface-700 mt-1 max-w-xl">{strategy.description}</p>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {strategy.tags.map((tag) => (
                <span key={tag} className="px-2 py-0.5 text-xs bg-surface-100 text-surface-600 rounded-full">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          {/* Aggregate stats */}
          {validPerfs.length > 0 ? (
            <>
              <div className="text-right">
                <p className="text-xs text-surface-500">Win Rate</p>
                <p className={`text-sm font-mono font-bold ${avgWinRate && avgWinRate > 50 ? "text-success-600" : "text-surface-900"}`}>
                  {avgWinRate !== null ? `${avgWinRate.toFixed(1)}%` : "—"}
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs text-surface-500">Avg Return</p>
                <p className={`text-sm font-mono font-bold ${avgReturn && avgReturn > 0 ? "text-success-600" : avgReturn && avgReturn < 0 ? "text-danger-600" : "text-surface-900"}`}>
                  {avgReturn !== null ? format.pct(avgReturn) : "—"}
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs text-surface-500">Sharpe</p>
                <p className="text-sm font-mono font-bold text-surface-900">
                  {avgSharpe !== null ? avgSharpe.toFixed(2) : "—"}
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs text-surface-500">Trades</p>
                <p className="text-sm font-mono font-bold text-surface-900">{totalTrades}</p>
              </div>
            </>
          ) : (
            <span className="text-xs text-surface-400">No backtest data yet</span>
          )}

          {expanded ? (
            <ChevronUp className="w-4 h-4 text-surface-300" />
          ) : (
            <ChevronDown className="w-4 h-4 text-surface-300" />
          )}
        </div>
      </div>

      {/* Expanded: per-instrument breakdown */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-surface-200">
          <p className="text-sm font-semibold text-surface-900 mb-3">
            Per-Instrument Backtest Results ({performances.length})
          </p>

          {performances.length === 0 ? (
            <p className="text-sm text-surface-500">
              No backtest results yet. Run backtests from the Backtests page to populate this.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-200">
                    <th className="text-left py-2 px-2 text-xs font-medium text-surface-500">Symbol</th>
                    <th className="text-right py-2 px-2 text-xs font-medium text-surface-500">Return</th>
                    <th className="text-right py-2 px-2 text-xs font-medium text-surface-500">Win Rate</th>
                    <th className="text-right py-2 px-2 text-xs font-medium text-surface-500">Sharpe</th>
                    <th className="text-right py-2 px-2 text-xs font-medium text-surface-500">Max DD</th>
                    <th className="text-right py-2 px-2 text-xs font-medium text-surface-500">Trades</th>
                    <th className="text-right py-2 px-2 text-xs font-medium text-surface-500">Payoff</th>
                    <th className="text-right py-2 px-2 text-xs font-medium text-surface-500">Run Date</th>
                  </tr>
                </thead>
                <tbody>
                  {performances.map((perf) => (
                    <tr key={perf.instrument_id} className="border-b border-surface-100 hover:bg-surface-50">
                      <td className="py-2 px-2 font-medium text-surface-900">{perf.symbol}</td>
                      <td className={`py-2 px-2 text-right font-mono ${(perf.total_return ?? 0) > 0 ? "text-success-600" : (perf.total_return ?? 0) < 0 ? "text-danger-600" : "text-surface-700"}`}>
                        {perf.total_return !== null ? format.pct(perf.total_return) : "—"}
                      </td>
                      <td className="py-2 px-2 text-right font-mono text-surface-900">
                        {perf.win_rate !== null ? `${perf.win_rate.toFixed(1)}%` : "—"}
                      </td>
                      <td className="py-2 px-2 text-right font-mono text-surface-900">
                        {perf.sharpe_ratio !== null ? perf.sharpe_ratio.toFixed(2) : "—"}
                      </td>
                      <td className="py-2 px-2 text-right font-mono text-danger-600">
                        {perf.max_drawdown !== null ? `${perf.max_drawdown.toFixed(1)}%` : "—"}
                      </td>
                      <td className="py-2 px-2 text-right font-mono text-surface-900">
                        {perf.total_trades ?? "—"}
                      </td>
                      <td className="py-2 px-2 text-right font-mono text-surface-900">
                        {perf.payoff_ratio !== null && perf.payoff_ratio !== Infinity
                          ? perf.payoff_ratio.toFixed(2)
                          : perf.payoff_ratio === Infinity
                          ? "∞"
                          : "—"}
                      </td>
                      <td className="py-2 px-2 text-right text-xs text-surface-500">
                        {new Date(perf.run_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {hasCaveat && (
            <div className="mt-3 p-2.5 rounded-lg bg-amber-50 border border-amber-200">
              <p className="text-xs text-amber-800 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                {performances.find((p) => p.data_caveat)?.data_caveat}
              </p>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

/* ── Main Page ── */

export default function StrategiesPage() {
  const [strategiesList, setStrategiesList] = useState<StrategyCard[]>([]);
  const [performances, setPerformances] = useState<PerformanceData[]>([]);
  const [loading, setLoading] = useState(true);
  const [horizonFilter, setHorizonFilter] = useState("");

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [strats, perfs] = await Promise.all([
          strategiesApi.list(horizonFilter || undefined),
          strategyPerformance.list(),
        ]);
        setStrategiesList(strats);
        setPerformances(perfs.items ?? []);
      } catch (e) {
        console.error("Failed to load strategies:", e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [horizonFilter]);

  // Group performances by strategy name
  const perfByStrategy = performances.reduce(
    (acc, p) => {
      (acc[p.strategy_name] = acc[p.strategy_name] || []).push(p);
      return acc;
    },
    {} as Record<string, PerformanceData[]>,
  );

  // Overall stats
  const strategiesWithBacktest = strategiesList.filter(
    (s) => (perfByStrategy[s.name]?.length ?? 0) > 0,
  );
  const totalBacktests = performances.length;

  return (
    <div>
      <Header
        title="Strategies"
        subtitle={`${strategiesList.length} registered strategies · ${totalBacktests} backtest results`}
        actions={
          <div className="flex items-center gap-2">
            <select
              value={horizonFilter}
              onChange={(e) => setHorizonFilter(e.target.value)}
              className="text-sm border border-surface-200 rounded-lg px-3 py-2"
            >
              <option value="">All Horizons</option>
              <option value="LONG_TERM">Long Term</option>
              <option value="SWING">Swing</option>
              <option value="INTRADAY">Intraday</option>
            </select>
          </div>
        }
      />

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card padding="sm">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded bg-primary-50">
              <Target className="w-4 h-4 text-primary-600" />
            </div>
            <div>
              <p className="text-xs text-surface-500">Total Strategies</p>
              <p className="text-lg font-bold text-surface-900">{strategiesList.length}</p>
            </div>
          </div>
        </Card>
        <Card padding="sm">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded bg-green-50">
              <BarChart3 className="w-4 h-4 text-success-600" />
            </div>
            <div>
              <p className="text-xs text-surface-500">With Backtests</p>
              <p className="text-lg font-bold text-surface-900">{strategiesWithBacktest.length}</p>
            </div>
          </div>
        </Card>
        <Card padding="sm">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded bg-blue-50">
              <Activity className="w-4 h-4 text-blue-600" />
            </div>
            <div>
              <p className="text-xs text-surface-500">Backtest Runs</p>
              <p className="text-lg font-bold text-surface-900">{totalBacktests}</p>
            </div>
          </div>
        </Card>
        <Card padding="sm">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded bg-amber-50">
              <Zap className="w-4 h-4 text-amber-600" />
            </div>
            <div>
              <p className="text-xs text-surface-500">Coverage</p>
              <p className="text-lg font-bold text-surface-900">
                {strategiesList.length > 0
                  ? `${Math.round((strategiesWithBacktest.length / strategiesList.length) * 100)}%`
                  : "—"}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Strategy cards */}
      {loading ? (
        <div className="h-64 flex items-center justify-center text-surface-700">
          <Loader2 className="w-5 h-5 animate-spin mr-2" />
          Loading strategies...
        </div>
      ) : strategiesList.length === 0 ? (
        <Card>
          <div className="h-64 flex flex-col items-center justify-center text-surface-700">
            <Target className="w-10 h-10 mb-2 text-surface-200" />
            <p className="font-medium">No strategies registered</p>
            <p className="text-sm text-surface-400 mt-1">
              Strategies are auto-discovered from the codebase on startup
            </p>
          </div>
        </Card>
      ) : (
        <div className="space-y-3">
          {strategiesList.map((strategy) => (
            <StrategyCardView
              key={strategy.name}
              strategy={strategy}
              performances={perfByStrategy[strategy.name] ?? []}
            />
          ))}
        </div>
      )}
    </div>
  );
}
