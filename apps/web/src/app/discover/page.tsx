"use client";

import { useState } from "react";
import { Compass, TrendingUp, TrendingDown, Plus, Loader2, Check, Sparkles, X } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { ConfirmationModal } from "@/components/ui/ConfirmationModal";
import { Header } from "@/components/layout/Header";
import { format } from "@/lib/format";
import { scanner, instruments as instrumentsApi } from "@/lib/api";

interface DiscoveryResult {
  symbol: string;
  name: string | null;
  last_price: number | null;
  change_pct: number | null;
  volume: number | null;
  market_cap: number | null;
  already_tracked: boolean;
}

const SCREENERS = [
  { value: "most_active", label: "Most Active" },
  { value: "day_gainers", label: "Day Gainers" },
  { value: "day_losers", label: "Day Losers" },
  { value: "growth_tech", label: "Growth Tech" },
  { value: "small_cap_gainers", label: "Small Cap Gainers" },
];

export default function DiscoverPage() {
  const [screener, setScreener] = useState("most_active");
  const [results, setResults] = useState<DiscoveryResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [addingSymbol, setAddingSymbol] = useState<string | null>(null);
  const [addedSymbols, setAddedSymbols] = useState<Set<string>>(new Set());
  const [analyzingSymbol, setAnalyzingSymbol] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [analysisError, setAnalysisError] = useState("");
  const [modalError, setModalError] = useState<string | null>(null);


  const runDiscovery = async (screenerValue: string) => {
    setLoading(true);
    setError("");
    try {
      const data = await scanner.discover(screenerValue, 25);
      setResults(data.results || []);
    } catch (err) {
      setError("Failed to load trending stocks. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleScreenerChange = (value: string) => {
    setScreener(value);
    runDiscovery(value);
  };

  const handleAdd = async (result: DiscoveryResult) => {
    setAddingSymbol(result.symbol);
    try {
      await instrumentsApi.create({
        symbol: result.symbol,
        name: result.name || result.symbol,
        type: "STOCK",
        currency: "USD",
      });
      setAddedSymbols((prev) => new Set(prev).add(result.symbol));
    } catch (err) {
      setModalError(`Failed to add ${result.symbol}. It may already exist.`);
    } finally {
      setAddingSymbol(null);
    }
  };

  const handleOpenChart = (result: DiscoveryResult) => {
    window.location.href = `/instruments/view?symbol=${result.symbol}`;
  };

  const handleAnalyze = async (result: DiscoveryResult) => {
    setAnalyzingSymbol(result.symbol);
    setAnalysisError("");
    setAnalysisResult(null);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

      // Ensure instrument exists
      let instrumentId: string | null = null;
      try {
        const createRes = await instrumentsApi.create({
          symbol: result.symbol,
          name: result.name || result.symbol,
          type: "STOCK",
          currency: "USD",
        });
        instrumentId = createRes.id;
        setAddedSymbols((prev) => new Set(prev).add(result.symbol));
      } catch {
        // Already exists — find it
        const searchRes = await fetch(`/api/v1/instruments?search=${result.symbol}&page_size=1`, {
          headers: authHeader,
        });
        if (searchRes.ok) {
          const data = await searchRes.json();
          instrumentId = data.items?.[0]?.id;
        }
      }

      if (!instrumentId) {
        setAnalysisError(`Could not find instrument ${result.symbol}`);
        return;
      }

      // Run consolidated analysis
      const res = await fetch(`/api/v1/signals/consolidated/${instrumentId}`, {
        method: "POST",
        headers: authHeader,
      });
      if (!res.ok) throw new Error("Analysis failed");
      const data = await res.json();
      setAnalysisResult(data);
    } catch (err: any) {
      setAnalysisError(err.message || "Analysis failed");
    } finally {
      setAnalyzingSymbol(null);
    }
  };

  return (
    <div>
      <Header
        title="Discover"
        subtitle="Trending and actively-traded stocks across the market — not just what you're tracking"
      />

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Compass className="w-4 h-4 text-primary-500" />
            <CardTitle>Market Screeners</CardTitle>
          </div>
        </CardHeader>

        <div className="flex flex-wrap gap-2 mb-4">
          {SCREENERS.map((s) => (
            <button
              key={s.value}
              onClick={() => handleScreenerChange(s.value)}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                screener === s.value
                  ? "bg-primary-600 text-white"
                  : "bg-surface-200 text-surface-700 hover:bg-surface-200"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="py-12 text-center text-surface-500">
            <Loader2 className="w-6 h-6 mx-auto mb-2 animate-spin" />
            Loading trending stocks...
          </div>
        ) : error ? (
          <div className="py-12 text-center text-danger-600">{error}</div>
        ) : results.length === 0 ? (
          <div className="py-12 text-center text-surface-500">
            Pick a screener above to see currently trending stocks.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-300 text-left">
                  <th className="py-2 px-3 text-surface-700 font-medium">Symbol</th>
                  <th className="py-2 px-3 text-surface-700 font-medium">Name</th>
                  <th className="py-2 px-3 text-surface-700 font-medium text-right">Price</th>
                  <th className="py-2 px-3 text-surface-700 font-medium text-right">Chg%</th>
                  <th className="py-2 px-3 text-surface-700 font-medium text-right">Volume</th>
                  <th className="py-2 px-3 text-surface-700 font-medium text-right">Market Cap</th>
                  <th className="py-2 px-3 text-surface-700 font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => {
                  const isPositive = (r.change_pct ?? 0) >= 0;
                  const alreadyAdded = r.already_tracked || addedSymbols.has(r.symbol);
                  return (
                    <tr
                      key={r.symbol}
                      className="border-b border-surface-200 hover:bg-surface-200 cursor-pointer"
                      onClick={() => handleOpenChart(r)}
                    >
                      <td className="py-2.5 px-3 font-semibold text-primary-600">
                        {r.symbol}
                      </td>
                      <td className="py-2.5 px-3 text-surface-900">{r.name ?? "—"}</td>
                      <td className="py-2.5 px-3 text-right font-mono">
                        {r.last_price != null ? format.currency(r.last_price) : "—"}
                      </td>
                      <td className={`py-2.5 px-3 text-right font-mono ${isPositive ? "text-success-600" : "text-danger-600"}`}>
                        <span className="inline-flex items-center gap-1 justify-end">
                          {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                          {r.change_pct != null ? `${r.change_pct.toFixed(2)}%` : "—"}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-surface-700">
                        {r.volume != null ? format.compact(r.volume) : "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-surface-700">
                        {r.market_cap != null ? format.compact(r.market_cap) : "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <div className="inline-flex items-center gap-1.5">
                          <button
                            onClick={(e) => { e.stopPropagation(); handleAnalyze(r); }}
                            disabled={analyzingSymbol === r.symbol}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-purple-600 border border-purple-200 rounded-lg hover:bg-purple-50 disabled:opacity-50"
                          >
                            {analyzingSymbol === r.symbol ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <Sparkles className="w-3 h-3" />
                            )}
                            Analyze
                          </button>
                          {!alreadyAdded && (
                            <button
                              onClick={(e) => { e.stopPropagation(); handleAdd(r); }}
                              disabled={addingSymbol === r.symbol}
                              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-primary-600 border border-primary-200 rounded-lg hover:bg-primary-50 disabled:opacity-50"
                            >
                              {addingSymbol === r.symbol ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <Plus className="w-3 h-3" />
                              )}
                              Add
                            </button>
                          )}
                          {alreadyAdded && !analyzingSymbol && (
                            <span className="inline-flex items-center gap-1 text-xs text-surface-500">
                              <Check className="w-3.5 h-3.5" /> Tracked
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Analysis Results */}
      {analysisError && (
        <Card className="mt-4 border-danger-200">
          <div className="flex items-center justify-between">
            <p className="text-sm text-danger-600">{analysisError}</p>
            <button onClick={() => setAnalysisError("")} className="text-xs text-surface-500 hover:text-surface-900">
              <X className="w-4 h-4" />
            </button>
          </div>
        </Card>
      )}
      {analyzingSymbol && !analysisResult && (
        <Card className="mt-4">
          <div className="flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-primary-500" />
            <p className="text-sm text-surface-700">Running full analysis on {analyzingSymbol}...</p>
          </div>
        </Card>
      )}
      {analysisResult && (
        <Card className="mt-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-semibold text-surface-900">Analysis: {analysisResult.symbol}</p>
            <div className="flex items-center gap-2">
              <a
                href={`/instruments/view?id=${analysisResult.instrument_id}`}
                className="text-xs text-primary-600 hover:text-primary-700 font-medium"
              >
                View Chart →
              </a>
              <button onClick={() => setAnalysisResult(null)} className="text-xs text-surface-500 hover:text-surface-900">
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2 mb-3">
            <span
              className={`px-3 py-1 rounded-full text-sm font-bold ${
                analysisResult.final_state === "ENTER_LONG"
                  ? "bg-green-50 text-success-600"
                  : analysisResult.final_state === "EXIT"
                  ? "bg-red-50 text-danger-600"
                  : analysisResult.final_state === "REDUCE"
                  ? "bg-amber-50 text-warning-600"
                  : "bg-surface-200 text-surface-700"
              }`}
            >
              {analysisResult.final_state === "ENTER_LONG" ? "BUY" :
               analysisResult.final_state === "EXIT" ? "SELL" :
               analysisResult.final_state === "REDUCE" ? "REDUCE" :
               analysisResult.final_state === "WATCH" ? "WATCH" : "HOLD"}
            </span>
            <span className="text-xs text-surface-500">
              {Math.round(analysisResult.final_confidence)}% confidence
            </span>
            {!analysisResult.llm_used && (
              <span className="text-xs text-warning-600">(mechanical vote only)</span>
            )}
          </div>

          <p className="text-sm text-surface-700 mb-3">{analysisResult.summary}</p>

          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs font-medium text-surface-900">Risk:</span>
            <span
              className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                analysisResult.risk_level === "LOW"
                  ? "bg-green-50 text-success-600"
                  : analysisResult.risk_level === "HIGH"
                  ? "bg-red-50 text-danger-600"
                  : "bg-amber-50 text-warning-600"
              }`}
            >
              {analysisResult.risk_level}
            </span>
            <span className="text-xs text-surface-500">{analysisResult.risk_reasoning}</span>
          </div>

          <div className="grid md:grid-cols-3 gap-4 mb-3">
            <div>
              <p className="text-xs font-medium text-surface-900 mb-1">Entry</p>
              <p className="text-sm text-surface-700">{analysisResult.entry_zone}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-danger-600 mb-1">Stop-Loss</p>
              <p className="text-sm text-surface-700">{analysisResult.stop_loss}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-success-600 mb-1">Take-Profit</p>
              <p className="text-sm text-surface-700">{analysisResult.take_profit}</p>
            </div>
          </div>

          {analysisResult.strategy_breakdown?.length > 0 && (
            <details className="pt-3 border-t border-surface-300">
              <summary className="text-xs font-medium text-surface-900 cursor-pointer">
                Strategy breakdown ({analysisResult.strategy_breakdown.length})
              </summary>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {analysisResult.strategy_breakdown.map((s: any, i: number) => (
                  <span key={i} className="text-xs px-2 py-1 rounded-lg bg-surface-200 text-surface-700">
                    {s.strategy}: {s.state}
                    {s.win_rate != null && <span className="ml-1 text-surface-500">({s.win_rate.toFixed(0)}% WR)</span>}
                  </span>
                ))}
              </div>
            </details>
          )}
        </Card>
      )}

      {/* Error Modal */}
      {modalError && (
        <ConfirmationModal
          title="Error"
          message={modalError}
          confirmLabel="OK"
          variant="warning"
          onConfirm={() => setModalError(null)}
          onCancel={() => setModalError(null)}
        />
      )}
    </div>
  );
}
