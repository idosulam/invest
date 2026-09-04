"use client";

import { useState, useEffect } from "react";
import { useInstruments } from "@/hooks/useApi";
import { signals as signalsApi } from "@/lib/api";
import Link from "next/link";
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Minus,
  Eye,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  Play,
  Filter,
  Sparkles,
  Loader2,
} from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";
import { format } from "@/lib/format";

/* ── Types ── */

interface SignalData {
  id: string;
  instrument_id: string;
  symbol: string | null;
  instrument_name: string | null;
  as_of: string;
  horizon: string;
  state: string;
  entry_zone_low: number | null;
  entry_zone_high: number | null;
  invalidation_rule: string | null;
  invalidation_level: number | null;
  target_method: string | null;
  target_price: number | null;
  max_loss_pct: number | null;
  suggested_size_pct: number | null;
  confidence: number;
  quality_gate: string;
  strategy_name: string | null;
  reason_codes: string[] | null;
  limitations: string[] | null;
  created_at: string;
}

/* ── State styling ── */

const STATE_CONFIG: Record<string, { color: string; bg: string; icon: any; label: string }> = {
  ENTER_LONG: { color: "text-success-600", bg: "bg-green-50", icon: TrendingUp, label: "Enter Long" },
  EXIT: { color: "text-danger-600", bg: "bg-red-50", icon: TrendingDown, label: "Exit" },
  REDUCE: { color: "text-warning-600", bg: "bg-amber-50", icon: Minus, label: "Reduce" },
  HOLD: { color: "text-primary-600", bg: "bg-blue-50", icon: Eye, label: "Hold" },
  WATCH: { color: "text-surface-700", bg: "bg-surface-100", icon: Eye, label: "Watch" },
  NO_SIGNAL: { color: "text-surface-200", bg: "bg-surface-50", icon: Minus, label: "No Signal" },
};

const STATE_GUIDANCE: Record<string, string> = {
  ENTER_LONG: "This strategy sees a buy setup right now. Consider entering within the entry zone below, with the stop-loss at the invalidation level.",
  EXIT: "This strategy is signaling to close an existing position in this stock — the setup that justified holding it has broken down.",
  REDUCE: "Consider trimming an existing position — the strategy sees rising risk but not a full exit signal yet.",
  HOLD: "No action needed. If you already hold this position, the strategy sees no reason to change it yet.",
  WATCH: "Not an entry yet. The strategy is tracking a potential setup — check back as conditions develop.",
  NO_SIGNAL: "This strategy found nothing actionable for this stock right now.",
};

const CONFIDENCE_EXPLAINER =
  "Confidence reflects how strongly the underlying data supports this signal — based on factors like how well similar setups have worked historically, current market conditions, and data quality. It is not a probability of profit, and even high-confidence signals can be wrong.";

const GATE_CONFIG: Record<string, { color: string; icon: any }> = {
  PASS: { color: "text-success-500", icon: CheckCircle },
  WARN: { color: "text-warning-500", icon: AlertTriangle },
  FAIL: { color: "text-danger-500", icon: XCircle },
};

/* ── Signal Card ── */

function SignalCard({ signal }: { signal: SignalData }) {
  const [expanded, setExpanded] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [loadingWhy, setLoadingWhy] = useState(false);

  const askWhy = async () => {
    setLoadingWhy(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const res = await fetch("/api/v1/assistant/query", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({
          question: `Why is this ${signal.state} signal active? What evidence supports it?`,
          instrument_id: signal.instrument_id,
          context_type: "signal",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setExplanation(data.answer);
      }
    } catch (e) { console.error(e); }
    finally { setLoadingWhy(false); }
  };
  const stateCfg = STATE_CONFIG[signal.state] || STATE_CONFIG.NO_SIGNAL;
  const gateCfg = GATE_CONFIG[signal.quality_gate] || GATE_CONFIG.WARN;
  const StateIcon = stateCfg.icon;
  const GateIcon = gateCfg.icon;

  return (
    <Card className="overflow-hidden">
      <div
        className="flex items-start justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start gap-3">
          {/* State badge */}
          <div className={`p-2.5 rounded-lg ${stateCfg.bg}`}>
            <StateIcon className={`w-5 h-5 ${stateCfg.color}`} />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <Link
                href={`/instruments/view?id=${signal.instrument_id}`}
                className="text-lg font-bold text-surface-900 hover:text-primary-600"
                onClick={(e) => e.stopPropagation()}
              >
                {signal.symbol ?? "—"}
              </Link>
              <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${stateCfg.bg} ${stateCfg.color}`}>
                {stateCfg.label}
              </span>
              <span className="px-2 py-0.5 text-xs bg-surface-100 text-surface-700 rounded-full">
                {signal.horizon}
              </span>
            </div>
            <p className="text-sm text-surface-700 mt-0.5">{signal.instrument_name}</p>
            <p className="text-xs text-surface-500 mt-1">
              {signal.strategy_name} · {new Date(signal.as_of).toLocaleDateString()}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Confidence */}
          <div className="text-right">
            <p className="text-xs text-surface-700 mb-1">Confidence</p>
            <div className="flex items-center gap-2">
              <div className="w-16 h-2 bg-surface-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    signal.confidence > 0.7 ? "bg-success-500" : signal.confidence > 0.4 ? "bg-warning-500" : "bg-danger-500"
                  }`}
                  style={{ width: `${signal.confidence * 100}%` }}
                />
              </div>
              <span className="text-sm font-mono font-medium">{(signal.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>

          {/* Quality gate */}
          <div className="flex items-center gap-1">
            <GateIcon className={`w-4 h-4 ${gateCfg.color}`} />
            <span className="text-xs font-medium">{signal.quality_gate}</span>
          </div>

          {/* Why? button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (explanation) {
                setExplanation(null);
              } else {
                askWhy();
              }
            }}
            disabled={loadingWhy}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-primary-600 border border-primary-200 rounded-lg hover:bg-primary-50 disabled:opacity-50"
          >
            {loadingWhy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
            {explanation ? "Hide" : "Why?"}
          </button>

          {/* Expand */}
          {expanded ? <ChevronUp className="w-4 h-4 text-surface-200" /> : <ChevronDown className="w-4 h-4 text-surface-200" />}
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-surface-200 space-y-4">
          {/* Plain-language guidance */}
          <div className={`rounded-lg p-3 text-sm ${stateCfg.bg} ${stateCfg.color}`}>
            <span className="font-medium">{stateCfg.label}:</span>{" "}
            {STATE_GUIDANCE[signal.state] ?? "No guidance available for this state."}
          </div>

          {/* Key levels */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {signal.entry_zone_low && signal.entry_zone_high && (
              <div>
                <p className="text-xs text-surface-700 mb-1">Entry Zone</p>
                <p className="font-mono text-sm text-surface-900">
                  {format.currency(signal.entry_zone_low)} — {format.currency(signal.entry_zone_high)}
                </p>
              </div>
            )}
            {signal.invalidation_level && (
              <div>
                <p className="text-xs text-surface-700 mb-1">Stop-Loss</p>
                <p className="font-mono text-sm text-danger-500">{format.currency(signal.invalidation_level)}</p>
                {signal.invalidation_rule && (
                  <p className="text-xs text-surface-500 mt-0.5">{signal.invalidation_rule}</p>
                )}
              </div>
            )}
            {signal.target_price && (
              <div>
                <p className="text-xs text-surface-700 mb-1">Take Profit</p>
                <p className="font-mono text-sm text-success-600">{format.currency(signal.target_price)}</p>
                <p className="text-xs text-surface-500 mt-0.5">2:1 reward-to-risk target</p>
              </div>
            )}
            {signal.max_loss_pct && (
              <div>
                <p className="text-xs text-surface-700 mb-1">Max Loss</p>
                <p className="font-mono text-sm text-surface-900">{signal.max_loss_pct}%</p>
              </div>
            )}
            {signal.suggested_size_pct && (
              <div>
                <p className="text-xs text-surface-700 mb-1">Position Size</p>
                <p className="font-mono text-sm text-surface-900">{signal.suggested_size_pct}%</p>
              </div>
            )}
          </div>

          {/* Target method */}
          {signal.target_method && (
            <div>
              <p className="text-xs text-surface-700 mb-1">Target Method</p>
              <span className="px-2 py-0.5 text-xs bg-surface-100 text-surface-700 rounded-full">
                {signal.target_method.replace(/_/g, " ")}
              </span>
            </div>
          )}

          {/* Confidence Breakdown */}
          <div>
            <p className="text-xs text-surface-700 mb-1">Confidence Breakdown</p>
            <p className="text-xs text-surface-500 mb-1.5">{CONFIDENCE_EXPLAINER}</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {[
                { label: "Strategy Validation", weight: "20%" },
                { label: "Regime Similarity", weight: "15%" },
                { label: "Feature Completeness", weight: "15%" },
                { label: "Signal Agreement", weight: "20%" },
                { label: "Liquidity", weight: "10%" },
                { label: "Model Calibration", weight: "10%" },
                { label: "Parameter Sensitivity", weight: "10%" },
              ].map((comp) => (
                <div key={comp.label} className="bg-surface-50 rounded p-2">
                  <p className="text-xs text-surface-700">{comp.label}</p>
                  <p className="text-xs text-surface-500">{comp.weight}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Reason codes */}
          {signal.reason_codes && signal.reason_codes.length > 0 && (
            <div>
              <p className="text-xs text-surface-700 mb-1.5">Evidence & Reasoning</p>
              <div className="flex flex-wrap gap-1.5">
                {signal.reason_codes.map((code, i) => (
                  <span key={i} className="px-2 py-0.5 text-xs bg-primary-50 text-primary-700 rounded-full">
                    {code.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Limitations */}
          {signal.limitations && signal.limitations.length > 0 && (
            <div>
              <p className="text-xs text-surface-700 mb-1.5">Limitations & Risks</p>
              <div className="flex flex-wrap gap-1.5">
                {signal.limitations.map((lim, i) => (
                  <span key={i} className="px-2 py-0.5 text-xs bg-amber-50 text-warning-600 rounded-full">
                    ⚠ {lim}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* AI Explanation */}
      {explanation && (
        <div className="mt-4 pt-4 border-t border-surface-200">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-primary-500" />
              <p className="text-sm font-medium text-surface-900">AI Analysis</p>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); setExplanation(null); }}
              className="text-xs text-surface-500 hover:text-surface-900"
            >
              Close
            </button>
          </div>
          <div className="text-sm text-surface-700 whitespace-pre-wrap bg-surface-50 rounded-lg p-3">
            {explanation}
          </div>
          <p className="text-xs text-surface-200 mt-2">
            ⚠️ Research analysis only — not financial advice.
          </p>
        </div>
      )}
    </Card>
  );
}

/* ── Main Page ── */

export default function SignalsPage() {
  const [signals, setSignals] = useState<SignalData[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [horizonFilter, setHorizonFilter] = useState("");
  const [stateFilter, setStateFilter] = useState("");

  useEffect(() => {
    const fetchSignals = async () => {
      setLoading(true);
      try {
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const params = new URLSearchParams();
        params.set("page_size", "100");
        if (horizonFilter) params.set("horizon", horizonFilter);
        if (stateFilter) params.set("state", stateFilter);

        const res = await fetch(`/api/v1/signals?${params}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const data = await res.json();
          setSignals(data.items);
          setTotal(data.total);
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchSignals();
  }, [horizonFilter, stateFilter]);

  const [generating, setGenerating] = useState(false);
  const [fullAnalysisResults, setFullAnalysisResults] = useState<any[]>([]);
  const [runningFull, setRunningFull] = useState(false);
  const [fullAnalysisError, setFullAnalysisError] = useState("");
  const [fullAnalysisProgress, setFullAnalysisProgress] = useState("");
  const [analysisMode, setAnalysisMode] = useState<"portfolio" | "discover" | null>(null);

  const runFullAnalysis = async (mode: "portfolio" | "discover") => {
    setRunningFull(true);
    setFullAnalysisError("");
    setFullAnalysisResults([]);
    setAnalysisMode(mode);

    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

      let instrumentsToAnalyze: { id: string; symbol: string }[] = [];

      if (mode === "portfolio") {
        setFullAnalysisProgress("Loading portfolio holdings...");
        const portRes = await fetch("/api/v1/portfolios", { headers: authHeader });
        if (!portRes.ok) throw new Error("Failed to load portfolios");
        const portfolios = await portRes.json();
        if (portfolios.length === 0) {
          setFullAnalysisError("No portfolios found — create one and add positions first.");
          setRunningFull(false);
          return;
        }
        // Use the first portfolio
        const posRes = await fetch(`/api/v1/portfolios/${portfolios[0].id}/positions`, { headers: authHeader });
        if (!posRes.ok) throw new Error("Failed to load positions");
        const positions = await posRes.json();
        instrumentsToAnalyze = positions.map((p: any) => ({ id: p.instrument_id, symbol: p.symbol }));

        if (instrumentsToAnalyze.length === 0) {
          setFullAnalysisError("Portfolio is empty — add some positions first.");
          setRunningFull(false);
          return;
        }
      } else {
        setFullAnalysisProgress("Loading tracked instruments...");
        const instRes = await fetch("/api/v1/instruments?page_size=100", { headers: authHeader });
        if (!instRes.ok) throw new Error("Failed to load instruments");
        const instData = await instRes.json();
        instrumentsToAnalyze = (instData.items || []).map((i: any) => ({ id: i.id, symbol: i.symbol }));

        if (instrumentsToAnalyze.length === 0) {
          setFullAnalysisError("No instruments tracked yet — add some first.");
          setRunningFull(false);
          return;
        }
      }

      const results: any[] = [];
      for (let i = 0; i < instrumentsToAnalyze.length; i++) {
        const inst = instrumentsToAnalyze[i];
        setFullAnalysisProgress(`Analyzing ${inst.symbol} (${i + 1}/${instrumentsToAnalyze.length})...`);
        try {
          const res = await fetch(`/api/v1/signals/consolidated/${inst.id}`, {
            method: "POST",
            headers: authHeader,
          });
          if (!res.ok) {
            results.push({ symbol: inst.symbol, error: "Analysis failed" });
            continue;
          }
          const data = await res.json();
          results.push(data);
        } catch (innerErr) {
          results.push({ symbol: inst.symbol, error: "Analysis failed for this instrument" });
        }
      }

      setFullAnalysisResults(results);
      setFullAnalysisProgress("");

      // Refresh the raw signals list underneath
      const params = new URLSearchParams();
      params.set("page_size", "100");
      if (horizonFilter) params.set("horizon", horizonFilter);
      if (stateFilter) params.set("state", stateFilter);
      const listRes = await fetch(`/api/v1/signals?${params}`, { headers: authHeader });
      if (listRes.ok) {
        const listData = await listRes.json();
        setSignals(listData.items);
        setTotal(listData.total);
      }
    } catch (e) {
      setFullAnalysisError("Full analysis failed — check that the local LLM (Ollama) is running.");
      console.error(e);
    } finally {
      setRunningFull(false);
      setFullAnalysisProgress("");
    }
  };

  const [genInstrumentId, setGenInstrumentId] = useState("");
  const generateSignals = async () => {
    if (!genInstrumentId) return;
    setGenerating(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const res = await fetch("/api/v1/signals/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ instrument_id: genInstrumentId }),
      });
      if (res.ok) {
        const data = await res.json();
        alert(`Generated ${data.signals_generated} signals`);
        // Refresh signals list
        window.location.reload();
      }
    } catch (e) { console.error(e); }
    finally { setGenerating(false); }
  };

  return (
    <div>
      <Header
        title="Signals"
        subtitle={`${total} active signals`}
        actions={
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={genInstrumentId}
              onChange={(e) => setGenInstrumentId(e.target.value)}
              placeholder="Instrument ID"
              className="text-sm border border-surface-200 rounded-lg px-3 py-2 w-48"
            />
            <button
              onClick={generateSignals}
              disabled={generating || !genInstrumentId}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {generating ? "Generating..." : "Generate"}
            </button>
            <button
              onClick={() => runFullAnalysis("portfolio")}
              disabled={runningFull}
              title="Run full analysis on your portfolio holdings with entry/stop/take profit recommendations"
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-purple-600 rounded-lg hover:bg-purple-700 disabled:opacity-50"
            >
              {runningFull && analysisMode === "portfolio"
                ? fullAnalysisProgress || "Analyzing..."
                : "Portfolio Analysis"}
            </button>
            <button
              onClick={() => runFullAnalysis("discover")}
              disabled={runningFull}
              title="Discover & analyze all tracked instruments with entry/stop/take profit recommendations"
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 disabled:opacity-50"
            >
              {runningFull && analysisMode === "discover"
                ? fullAnalysisProgress || "Analyzing..."
                : "Discover → Analyze"}
            </button>
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
            <select
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value)}
              className="text-sm border border-surface-200 rounded-lg px-3 py-2"
            >
              <option value="">All States</option>
              <option value="ENTER_LONG">Enter Long</option>
              <option value="EXIT">Exit</option>
              <option value="REDUCE">Reduce</option>
              <option value="HOLD">Hold</option>
              <option value="WATCH">Watch</option>
            </select>
          </div>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        {["ENTER_LONG", "EXIT", "REDUCE", "HOLD", "WATCH"].map((state) => {
          const cfg = STATE_CONFIG[state];
          const count = signals.filter((s) => s.state === state).length;
          const Icon = cfg.icon;
          return (
            <Card key={state} padding="sm">
              <div className="flex items-center gap-2">
                <div className={`p-1.5 rounded ${cfg.bg}`}>
                  <Icon className={`w-4 h-4 ${cfg.color}`} />
                </div>
                <div>
                  <p className="text-xs text-surface-700">{cfg.label}</p>
                  <p className="text-lg font-bold text-surface-900">{count}</p>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Full Analysis results */}
      {fullAnalysisError && (
        <Card className="mb-6 border-danger-200">
          <p className="text-sm text-danger-600">{fullAnalysisError}</p>
        </Card>
      )}
      {runningFull && (
        <Card className="mb-6">
          <p className="text-sm text-surface-700">{fullAnalysisProgress || "Analyzing..."}</p>
        </Card>
      )}
      {fullAnalysisResults.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-semibold text-surface-900">
              Final Verdicts — {fullAnalysisResults.length} stocks
              {analysisMode === "portfolio" ? " (Portfolio)" : " (All Tracked)"}
            </p>
            <button
              onClick={() => setFullAnalysisResults([])}
              className="text-xs text-surface-500 hover:text-surface-900"
            >
              Close all
            </button>
          </div>
          <div className="space-y-3">
            {fullAnalysisResults.map((item: any, idx: number) => {
              if (item.error) {
                return (
                  <Card key={idx} className="border-danger-200">
                    <p className="text-sm font-semibold text-surface-900">{item.symbol}</p>
                    <p className="text-sm text-danger-600">{item.error}</p>
                  </Card>
                );
              }
              const actionLabel =
                item.final_state === "ENTER_LONG" ? "BUY" :
                item.final_state === "EXIT" ? "SELL" :
                item.final_state === "REDUCE" ? "REDUCE" :
                item.final_state === "WATCH" ? "WATCH" : "HOLD";
              return (
                <Card key={idx}>
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-semibold text-surface-900">{item.symbol}</p>
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-3 py-1 rounded-full text-sm font-bold ${
                          actionLabel === "BUY"
                            ? "bg-green-50 text-success-600"
                            : actionLabel === "SELL"
                            ? "bg-red-50 text-danger-600"
                            : actionLabel === "REDUCE"
                            ? "bg-amber-50 text-warning-600"
                            : "bg-surface-100 text-surface-700"
                        }`}
                      >
                        {actionLabel}
                      </span>
                      <span className="text-xs text-surface-500">
                        {Math.round(item.final_confidence)}% confidence
                      </span>
                      {!item.llm_used && (
                        <span className="text-xs text-warning-600">(mechanical vote only)</span>
                      )}
                    </div>
                  </div>

                  <p className="text-sm text-surface-700 mb-3">{item.summary}</p>

                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xs font-medium text-surface-900">Risk:</span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        item.risk_level === "LOW"
                          ? "bg-green-50 text-success-600"
                          : item.risk_level === "HIGH"
                          ? "bg-red-50 text-danger-600"
                          : "bg-amber-50 text-warning-600"
                      }`}
                    >
                      {item.risk_level}
                    </span>
                    <span className="text-xs text-surface-500">{item.risk_reasoning}</span>
                  </div>

                  <div className="grid md:grid-cols-3 gap-4 mb-3">
                    <div>
                      <p className="text-xs font-medium text-surface-900 mb-1">Entry</p>
                      <p className="text-sm text-surface-700">{item.entry_zone}</p>
                    </div>
                    <div>
                      <p className="text-xs font-medium text-danger-600 mb-1">Stop-Loss</p>
                      <p className="text-sm text-surface-700">{item.stop_loss}</p>
                    </div>
                    <div>
                      <p className="text-xs font-medium text-success-600 mb-1">Take-Profit</p>
                      <p className="text-sm text-surface-700">{item.take_profit}</p>
                    </div>
                  </div>

                  {item.strategy_breakdown?.length > 0 && (
                    <details className="pt-3 border-t border-surface-200">
                      <summary className="text-xs font-medium text-surface-900 cursor-pointer">
                        Show strategy breakdown ({item.strategy_breakdown.length})
                      </summary>
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {item.strategy_breakdown.map((s: any, sidx: number) => (
                          <span
                            key={sidx}
                            className="text-xs px-2 py-1 rounded-lg bg-surface-100 text-surface-700"
                          >
                            {s.strategy}: {s.state}
                            {s.win_rate != null && (
                              <span className="ml-1 text-surface-500">({s.win_rate.toFixed(0)}% WR)</span>
                            )}
                          </span>
                        ))}
                      </div>
                    </details>
                  )}

                  <p className="text-xs text-surface-400 pt-3 border-t border-surface-200 mt-3">
                    Combines technical strategies, news, and congressional trading activity.
                    Does not yet include institutional 13F filings. This is reasoning over
                    available evidence, not a statistical forecast.
                  </p>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      <details className="mb-3">
        <summary className="text-sm text-surface-500 cursor-pointer">
          Show individual technical strategy signals ({total})
        </summary>

      {/* Signal cards */}
      {loading ? (
        <div className="h-64 flex items-center justify-center text-surface-700">Loading signals...</div>
      ) : signals.length === 0 ? (
        <Card>
          <div className="h-64 flex flex-col items-center justify-center text-surface-700">
            <Activity className="w-10 h-10 mb-2 text-surface-200" />
            <p className="font-medium">No signals yet</p>
            <p className="text-sm text-surface-200 mt-1">
              Run signal generation from the API or add instruments with bar data
            </p>
          </div>
        </Card>
      ) : (
        <div className="space-y-3">
          {signals.map((signal) => (
            <SignalCard key={signal.id} signal={signal} />
          ))}
        </div>
      )}
      </details>
    </div>
  );
}
