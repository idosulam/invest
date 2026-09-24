"use client";

import { useState, useEffect, useRef } from "react";
import { useInstruments } from "@/hooks/useApi";
import { signals as signalsApi, analysis } from "@/lib/api";
import type { AnalysisJobStatus } from "@/lib/api";
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

/* ── Full-analysis result types (consolidated signal) ── */

interface LadderRung {
  trigger: string;
  fraction: number; // fraction of the intended position to deploy here (0..1)
  note: string;
}

interface EntryPlan {
  plain_language: string;
  dream_entry: number;
  prob_reach_entry: number; // 0..1 — P(touch dream_entry within horizon)
  likely_to_miss: boolean;
  expected_entry: number | null;
  ladders: LadderRung[];
  win_before_stop?: number; // 0..1
}

interface PortfolioAction {
  action: "INITIATE" | "ADD" | "TRIM" | "EXIT" | "HOLD" | "WATCH" | "AVOID";
  trade_shares: number; // signed: +buy / -sell
  trade_value: number; // signed $
  trade_pct_of_position: number; // 0..1 of current position
  new_weight: number; // 0..1 projected weight after the trade
  pnl_pct: number; // fraction return vs entry (0.05 = +5%)
  rationale: string;
}

interface StrategyBreakdownItem {
  strategy: string;
  state: string;
  win_rate?: number | null;
}

interface FullAnalysisItem {
  instrument_id?: string;
  symbol?: string | null;
  final_state?: string;
  final_confidence?: number;
  summary?: string | null;
  entry_zone?: string | null;
  stop_loss?: string | null;
  take_profit?: string | null;
  risk_level?: string | null;
  risk_reasoning?: string | null;
  strategy_breakdown?: StrategyBreakdownItem[] | null;
  llm_used?: boolean;
  current_price?: number | null;
  horizon_days?: number | null;
  till_date?: string | null;
  entry_probability?: number | null;
  entry_plan?: EntryPlan | null;
  portfolio_action?: PortfolioAction | null;
  error?: string | null;
}

/* ── State styling ── */

const STATE_CONFIG: Record<string, { color: string; bg: string; icon: any; label: string }> = {
  ENTER_LONG: { color: "text-success-600", bg: "bg-green-50", icon: TrendingUp, label: "Enter Long" },
  EXIT: { color: "text-danger-600", bg: "bg-red-50", icon: TrendingDown, label: "Exit" },
  REDUCE: { color: "text-warning-600", bg: "bg-amber-50", icon: Minus, label: "Reduce" },
  HOLD: { color: "text-primary-600", bg: "bg-blue-50", icon: Eye, label: "Hold" },
  WATCH: { color: "text-surface-700", bg: "bg-surface-200", icon: Eye, label: "Watch" },
  NO_SIGNAL: { color: "text-surface-400", bg: "bg-surface-200", icon: Minus, label: "No Signal" },
};

/* ── Portfolio-action styling ── */

const ACTION_CONFIG: Record<string, { color: string; bg: string; icon: any; label: string }> = {
  INITIATE: { color: "text-success-600", bg: "bg-green-50", icon: TrendingUp, label: "Initiate" },
  ADD: { color: "text-success-600", bg: "bg-green-50", icon: TrendingUp, label: "Add" },
  TRIM: { color: "text-warning-600", bg: "bg-amber-50", icon: Minus, label: "Trim" },
  EXIT: { color: "text-danger-600", bg: "bg-red-50", icon: TrendingDown, label: "Exit" },
  HOLD: { color: "text-primary-600", bg: "bg-blue-50", icon: Eye, label: "Hold" },
  WATCH: { color: "text-surface-700", bg: "bg-surface-200", icon: Eye, label: "Watch" },
  AVOID: { color: "text-danger-600", bg: "bg-red-50", icon: XCircle, label: "Avoid" },
};

/* ── Small helpers ── */

/** "just now" / "3m ago" / "2h ago" / "5d ago" */
function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const secs = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (secs < 60) return "just now";
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** "Sep 30" from an ISO date string (timezone-safe for date-only strings) */
function formatTillDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  const d = m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

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

/* ── Full-analysis detail blocks ── */

function PortfolioActionBlock({ action }: { action: PortfolioAction }) {
  const cfg = ACTION_CONFIG[action.action] || ACTION_CONFIG.WATCH;
  const ActionIcon = cfg.icon;
  const shares = Math.abs(action.trade_shares);
  const value = Math.abs(action.trade_value);
  return (
    <div className="rounded-lg bg-surface-200 p-3 mb-3">
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full ${cfg.bg} ${cfg.color}`}>
          <ActionIcon className="w-3 h-3" />
          {cfg.label}
        </span>
        <span className={`text-xs font-mono font-medium ${format.changeColor(action.pnl_pct)}`}>
          P&L {format.pct(action.pnl_pct * 100, 1)}
        </span>
        {(shares > 0 || value > 0) && (
          <span className="text-xs text-surface-700">
            {action.trade_shares < 0 ? "Sell" : "Buy"}{" "}
            {shares.toLocaleString(undefined, { maximumFractionDigits: 2 })} sh ·{" "}
            {format.currency(value)}
            {action.trade_pct_of_position > 0 && (
              <span className="text-surface-500"> ({Math.round(action.trade_pct_of_position * 100)}% of position)</span>
            )}
          </span>
        )}
        <span className="text-xs text-surface-500">Target weight {Math.round(action.new_weight * 100)}%</span>
      </div>
      <p className="text-xs text-surface-700 mt-1.5">{action.rationale}</p>
    </div>
  );
}

function EntryPlanBlock({ plan }: { plan: EntryPlan }) {
  const asPct = (v: number) => `${Math.round(v * 100)}%`;
  return (
    <div className="rounded-lg bg-surface-200 p-3 mb-3">
      <p className="text-xs font-medium text-surface-900 mb-1">Entry Plan</p>
      <p className="text-sm text-surface-700 mb-2">{plan.plain_language}</p>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="px-2 py-0.5 text-xs font-mono bg-primary-50 text-primary-700 rounded-full">
          P(reach {format.currency(plan.dream_entry)}) = {asPct(plan.prob_reach_entry)}
        </span>
        {plan.likely_to_miss && (
          <span className="px-2 py-0.5 text-xs bg-amber-50 text-warning-600 rounded-full">Likely to miss</span>
        )}
        {plan.expected_entry != null && (
          <span className="text-xs text-surface-700">
            Expected entry: <span className="font-mono">{format.currency(plan.expected_entry)}</span>
          </span>
        )}
        {plan.win_before_stop != null && (
          <span className="text-xs text-surface-700">
            P(win before stop) = <span className="font-mono">{asPct(plan.win_before_stop)}</span>
          </span>
        )}
      </div>
      {plan.ladders.length > 0 && (
        <ul className="mt-2 space-y-0.5">
          {plan.ladders.map((rung, i) => (
            <li key={i} className="text-xs text-surface-700">
              <span className="font-mono">{asPct(rung.fraction)}</span> — {rung.trigger}
              {rung.note ? <span className="text-surface-500"> ({rung.note})</span> : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

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

  const navigateToInstrument = () => {
    window.location.href = `/instruments/view?id=${signal.instrument_id}`;
  };

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
              <span className="px-2 py-0.5 text-xs bg-surface-200 text-surface-700 rounded-full">
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
              <div className="w-16 h-2 bg-surface-200 rounded-full overflow-hidden">
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

          {/* Chart link */}
          <button
            onClick={(e) => { e.stopPropagation(); navigateToInstrument(); }}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-primary-600 border border-primary-200 rounded-lg hover:bg-primary-50"
          >
            Chart →
          </button>

          {/* Expand */}
          {expanded ? <ChevronUp className="w-4 h-4 text-surface-400" /> : <ChevronDown className="w-4 h-4 text-surface-400" />}
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-surface-300 space-y-4">
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
              <span className="px-2 py-0.5 text-xs bg-surface-200 text-surface-700 rounded-full">
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
                <div key={comp.label} className="bg-surface-200 rounded p-2">
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
        <div className="mt-4 pt-4 border-t border-surface-300">
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
          <div className="text-sm text-surface-700 whitespace-pre-wrap bg-surface-200 rounded-lg p-3">
            {explanation}
          </div>
          <p className="text-xs text-surface-400 mt-2">
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
  const [fullAnalysisResults, setFullAnalysisResults] = useState<FullAnalysisItem[]>([]);
  const [runningFull, setRunningFull] = useState(false);
  const [fullAnalysisError, setFullAnalysisError] = useState("");
  const [fullAnalysisProgress, setFullAnalysisProgress] = useState("");
  const [analysisMode, setAnalysisMode] = useState<"portfolio" | "discover" | null>(null);
  const [lastRunAt, setLastRunAt] = useState<{ portfolio: string | null; discover: string | null }>({
    portfolio: null,
    discover: null,
  });
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollFailuresRef = useRef(0);
  const pollInFlightRef = useRef(false);

  /* ── Last-run badge ── */

  const refreshLastRun = async (mode: "portfolio" | "discover") => {
    try {
      const data = await analysis.lastRun(mode);
      const at = data.last_run_at ?? null;
      setLastRunAt((prev) =>
        mode === "portfolio" ? { ...prev, portfolio: at } : { ...prev, discover: at },
      );
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    refreshLastRun("portfolio");
    refreshLastRun("discover");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── Background job polling (non-blocking; cleared on unmount) ── */

  const stopPolling = () => {
    if (pollTimerRef.current !== null) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  // If the user navigates away, stop polling — the job keeps running server-side
  // and the results are persisted, so nothing is lost.
  useEffect(() => () => stopPolling(), []);

  const refreshSignalsList = async () => {
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const params = new URLSearchParams();
      params.set("page_size", "100");
      if (horizonFilter) params.set("horizon", horizonFilter);
      if (stateFilter) params.set("state", stateFilter);
      const listRes = await fetch(`/api/v1/signals?${params}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (listRes.ok) {
        const listData = await listRes.json();
        setSignals(listData.items);
        setTotal(listData.total);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const startJobPolling = (jobId: string, mode: "portfolio" | "discover") => {
    stopPolling();
    pollFailuresRef.current = 0;

    const tick = async () => {
      if (pollInFlightRef.current) return;
      pollInFlightRef.current = true;
      try {
        let job: AnalysisJobStatus;
        try {
          job = await analysis.job(jobId);
          pollFailuresRef.current = 0;
        } catch (pollErr) {
          // Transient poll failure — keep trying a few times before giving up.
          console.error(pollErr);
          pollFailuresRef.current += 1;
          if (pollFailuresRef.current >= 5) {
            stopPolling();
            setRunningFull(false);
            setFullAnalysisProgress("");
            setFullAnalysisError(
              "Lost contact while the analysis was running — it continues in the background; run it again later to pick up the results.",
            );
          }
          return;
        }

        if (job.status === "RUNNING") {
          const done = job.progress?.done ?? 0;
          const total = job.progress?.total ?? 0;
          setFullAnalysisProgress(total > 0 ? `Analyzing ${done}/${total}...` : "Analyzing...");
          return;
        }

        stopPolling();
        setRunningFull(false);
        setFullAnalysisProgress("");

        if (job.status === "FAILED") {
          setFullAnalysisError(
            job.error || "Full analysis failed — check that the local LLM (Ollama) is running.",
          );
        } else {
          setFullAnalysisResults(job.results ?? []);
          await refreshSignalsList();
        }
        refreshLastRun(mode);
      } finally {
        pollInFlightRef.current = false;
      }
    };

    tick();
    pollTimerRef.current = setInterval(tick, 2500);
  };

  const runFullAnalysis = async (mode: "portfolio" | "discover") => {
    setRunningFull(true);
    setFullAnalysisError("");
    setFullAnalysisResults([]);
    setAnalysisMode(mode);
    setFullAnalysisProgress("Starting background analysis...");

    try {
      // Kick off the run server-side — the heavy LLM chain runs in a background
      // job, so the UI stays responsive and we only poll lightweight status.
      const job = await analysis.run({ scope: mode });
      setFullAnalysisProgress(job.total > 0 ? `Analyzing 0/${job.total}...` : "Analyzing...");
      startJobPolling(job.job_id, mode);
    } catch (e) {
      console.error(e);
      setFullAnalysisError(
        "Failed to start full analysis — check that the backend (and local LLM) is running.",
      );
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
        // Signals generated successfully — refresh the list
        await refreshSignalsList();
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
              className="text-sm border border-surface-300 rounded-lg px-3 py-2 w-48"
            />
            <button
              onClick={generateSignals}
              disabled={generating || !genInstrumentId}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {generating ? "Generating..." : "Generate"}
            </button>
            <div className="flex flex-col gap-0.5">
              <button
                onClick={() => runFullAnalysis("portfolio")}
                disabled={runningFull}
                title="Run full analysis on your portfolio holdings with entry/stop/take profit recommendations"
                className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-purple-600 rounded-lg hover:bg-purple-700 disabled:opacity-50"
              >
                {runningFull && analysisMode === "portfolio" ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    {fullAnalysisProgress || "Analyzing..."}
                  </>
                ) : (
                  "Portfolio Analysis"
                )}
              </button>
              {lastRunAt.portfolio && (
                <span className="text-[10px] text-surface-500 px-1 whitespace-nowrap">
                  Last run {timeAgo(lastRunAt.portfolio)}
                </span>
              )}
            </div>
            <div className="flex flex-col gap-0.5">
              <button
                onClick={() => runFullAnalysis("discover")}
                disabled={runningFull}
                title="Discover & analyze all tracked instruments with entry/stop/take profit recommendations"
                className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 disabled:opacity-50"
              >
                {runningFull && analysisMode === "discover" ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    {fullAnalysisProgress || "Analyzing..."}
                  </>
                ) : (
                  "Discover → Analyze"
                )}
              </button>
              {lastRunAt.discover && (
                <span className="text-[10px] text-surface-500 px-1 whitespace-nowrap">
                  Last run {timeAgo(lastRunAt.discover)}
                </span>
              )}
            </div>
            <select
              value={horizonFilter}
              onChange={(e) => setHorizonFilter(e.target.value)}
              className="text-sm border border-surface-300 rounded-lg px-3 py-2"
            >
              <option value="">All Horizons</option>
              <option value="LONG_TERM">Long Term</option>
              <option value="SWING">Swing</option>
              <option value="INTRADAY">Intraday</option>
            </select>
            <select
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value)}
              className="text-sm border border-surface-300 rounded-lg px-3 py-2"
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
          <div className="flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-surface-500" />
            <p className="text-sm text-surface-700">{fullAnalysisProgress || "Analyzing..."}</p>
          </div>
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
            {fullAnalysisResults.map((item: FullAnalysisItem, idx: number) => {
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
              const pa = item.portfolio_action;
              const plan = item.entry_plan;
              const breakdown = item.strategy_breakdown ?? [];
              return (
                <Card key={idx} className="cursor-pointer hover:ring-2 hover:ring-primary-300 transition-all" onClick={() => {
                  if (item.instrument_id) window.location.href = `/instruments/view?id=${item.instrument_id}`;
                }}>
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
                            : "bg-surface-200 text-surface-700"
                        }`}
                      >
                        {actionLabel}
                      </span>
                      <span className="text-xs text-surface-500">
                        {Math.round(item.final_confidence ?? 0)}% confidence
                      </span>
                      {item.till_date && (
                        <span className="text-xs text-surface-500">
                          Till {formatTillDate(item.till_date)}
                          {item.horizon_days != null ? ` (${item.horizon_days}d)` : ""}
                        </span>
                      )}
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

                  {/* Portfolio-aware action */}
                  {pa && <PortfolioActionBlock action={pa} />}

                  {/* Probabilistic entry plan */}
                  {plan && <EntryPlanBlock plan={plan} />}

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

                  {breakdown.length > 0 && (
                    <details className="pt-3 border-t border-surface-300">
                      <summary className="text-xs font-medium text-surface-900 cursor-pointer">
                        Show strategy breakdown ({breakdown.length})
                      </summary>
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {breakdown.map((s: StrategyBreakdownItem, sidx: number) => (
                          <span
                            key={sidx}
                            className="text-xs px-2 py-1 rounded-lg bg-surface-200 text-surface-700"
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

                  <p className="text-xs text-surface-400 pt-3 border-t border-surface-300 mt-3">
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
            <Activity className="w-10 h-10 mb-2 text-surface-400" />
            <p className="font-medium">No signals yet</p>
            <p className="text-sm text-surface-400 mt-1">
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
