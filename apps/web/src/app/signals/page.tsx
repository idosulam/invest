"use client";

import { useState, useEffect } from "react";
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
                href={`/instruments/${signal.instrument_id}`}
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
            <p className="text-xs text-surface-200 mt-1">
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
            onClick={(e) => { e.stopPropagation(); askWhy(); }}
            disabled={loadingWhy}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-primary-600 border border-primary-200 rounded-lg hover:bg-primary-50 disabled:opacity-50"
          >
            {loadingWhy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
            Why?
          </button>

          {/* Expand */}
          {expanded ? <ChevronUp className="w-4 h-4 text-surface-200" /> : <ChevronDown className="w-4 h-4 text-surface-200" />}
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-surface-200 space-y-4">
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
                <p className="text-xs text-surface-700 mb-1">Invalidation</p>
                <p className="font-mono text-sm text-danger-500">{format.currency(signal.invalidation_level)}</p>
                {signal.invalidation_rule && (
                  <p className="text-xs text-surface-200 mt-0.5">{signal.invalidation_rule}</p>
                )}
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
            <p className="text-xs text-surface-700 mb-1.5">Confidence Breakdown</p>
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
                  <p className="text-xs text-surface-200">{comp.weight}</p>
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
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="w-4 h-4 text-primary-500" />
            <p className="text-sm font-medium text-surface-900">AI Analysis</p>
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
    </div>
  );
}
