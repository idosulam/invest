"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import {
  ScanLine,
  Play,
  ChevronUp,
  ChevronDown,
  Filter,
  X,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";
import { format } from "@/lib/format";

/* ── Types ── */

interface ScanResult {
  instrument_id: string;
  symbol: string;
  name: string;
  type: string;
  exchange: string | null;
  sector: string | null;
  last_price: number | null;
  change_pct: number | null;
  volume_avg_20d: number | null;
  rsi_14: number | null;
  sma_20: number | null;
  sma_50: number | null;
  sma_200: number | null;
  atr_14: number | null;
  adx_14: number | null;
  bb_pct_b: number | null;
  above_sma_200: boolean | null;
  sma_20_above_50: boolean | null;
  pe_ratio: number | null;
  market_cap: number | null;
}

interface ScanFilters {
  min_rsi: string;
  max_rsi: string;
  above_sma_200: string; // "true" | "false" | ""
  sma_20_above_50: string;
  min_adx: string;
  bb_oversold: boolean;
  bb_overbought: boolean;
  min_volume_avg: string;
  max_pe: string;
  min_pe: string;
  min_market_cap: string;
  instrument_type: string;
  sector: string;
}

const EMPTY_FILTERS: ScanFilters = {
  min_rsi: "",
  max_rsi: "",
  above_sma_200: "",
  sma_20_above_50: "",
  min_adx: "",
  bb_oversold: false,
  bb_overbought: false,
  min_volume_avg: "",
  max_pe: "",
  min_pe: "",
  min_market_cap: "",
  instrument_type: "",
  sector: "",
};

type SortField =
  | "symbol"
  | "last_price"
  | "change_pct"
  | "volume_avg_20d"
  | "rsi_14"
  | "adx_14"
  | "bb_pct_b"
  | "pe_ratio"
  | "market_cap";

/* ── Page ── */

export default function ScannerPage() {
  const [filters, setFilters] = useState<ScanFilters>(EMPTY_FILTERS);
  const [results, setResults] = useState<ScanResult[]>([]);
  const [total, setTotal] = useState(0);
  const [scanTime, setScanTime] = useState(0);
  const [loading, setLoading] = useState(false);
  const [hasScanned, setHasScanned] = useState(false);
  const [sortField, setSortField] = useState<SortField>("symbol");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [showFilters, setShowFilters] = useState(true);

  const runScan = useCallback(async () => {
    setLoading(true);
    setHasScanned(true);

    const body: Record<string, any> = {};
    if (filters.min_rsi) body.min_rsi = Number(filters.min_rsi);
    if (filters.max_rsi) body.max_rsi = Number(filters.max_rsi);
    if (filters.above_sma_200)
      body.above_sma_200 = filters.above_sma_200 === "true";
    if (filters.sma_20_above_50)
      body.sma_20_above_50 = filters.sma_20_above_50 === "true";
    if (filters.min_adx) body.min_adx = Number(filters.min_adx);
    if (filters.bb_oversold) body.bb_oversold = true;
    if (filters.bb_overbought) body.bb_overbought = true;
    if (filters.min_volume_avg)
      body.min_volume_avg = Number(filters.min_volume_avg);
    if (filters.max_pe) body.max_pe = Number(filters.max_pe);
    if (filters.min_pe) body.min_pe = Number(filters.min_pe);
    if (filters.min_market_cap)
      body.min_market_cap = Number(filters.min_market_cap);
    if (filters.instrument_type) body.instrument_type = filters.instrument_type;
    if (filters.sector) body.sector = filters.sector;

    try {
      const token =
        typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const res = await fetch(
        `/api/v1/scanner/run?sort_by=${sortField}&sort_dir=${sortDir}&limit=200`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(body),
        },
      );

      if (!res.ok) throw new Error("Scan failed");
      const data = await res.json();
      setResults(data.results);
      setTotal(data.total);
      setScanTime(data.scan_time_ms);
    } catch (err) {
      console.error(err);
      setResults([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [filters, sortField, sortDir]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  };

  const activeFilterCount = Object.entries(filters).filter(([k, v]) => {
    if (typeof v === "boolean") return v;
    return v !== "";
  }).length;

  return (
    <div>
      <Header
        title="Scanner"
        subtitle="Filter instruments by technical and fundamental criteria"
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowFilters((s) => !s)}
              className="flex items-center gap-1.5 px-3 py-2 text-sm border border-surface-200 rounded-lg hover:bg-surface-50"
            >
              <Filter className="w-4 h-4" />
              Filters
              {activeFilterCount > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-primary-100 text-primary-700 rounded-full">
                  {activeFilterCount}
                </span>
              )}
            </button>
            <button
              onClick={runScan}
              disabled={loading}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              <Play className="w-4 h-4" />
              {loading ? "Scanning..." : "Run Scan"}
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* ── Filters Panel ── */}
        {showFilters && (
          <div className="lg:col-span-1">
            <Card>
              <CardHeader>
                <CardTitle>Filters</CardTitle>
                {activeFilterCount > 0 && (
                  <button
                    onClick={() => setFilters(EMPTY_FILTERS)}
                    className="text-xs text-surface-700 hover:text-surface-900 flex items-center gap-1"
                  >
                    <X className="w-3 h-3" /> Clear
                  </button>
                )}
              </CardHeader>

              <div className="space-y-5">
                {/* Instrument Type */}
                <FilterGroup label="Instrument Type">
                  <select
                    value={filters.instrument_type}
                    onChange={(e) =>
                      setFilters((f) => ({
                        ...f,
                        instrument_type: e.target.value,
                      }))
                    }
                    className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2"
                  >
                    <option value="">All</option>
                    <option value="STOCK">Stock</option>
                    <option value="ETF">ETF</option>
                    <option value="BENCHMARK">Benchmark</option>
                  </select>
                </FilterGroup>

                {/* RSI */}
                <FilterGroup label="RSI (14)">
                  <div className="flex gap-2">
                    <input
                      type="number"
                      placeholder="Min"
                      value={filters.min_rsi}
                      onChange={(e) =>
                        setFilters((f) => ({ ...f, min_rsi: e.target.value }))
                      }
                      className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2"
                    />
                    <input
                      type="number"
                      placeholder="Max"
                      value={filters.max_rsi}
                      onChange={(e) =>
                        setFilters((f) => ({ ...f, max_rsi: e.target.value }))
                      }
                      className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2"
                    />
                  </div>
                </FilterGroup>

                {/* Trend */}
                <FilterGroup label="Trend">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={filters.above_sma_200 === "true"}
                      onChange={(e) =>
                        setFilters((f) => ({
                          ...f,
                          above_sma_200: e.target.checked ? "true" : "",
                        }))
                      }
                      className="rounded border-surface-200"
                    />
                    Price above SMA 200
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={filters.sma_20_above_50 === "true"}
                      onChange={(e) =>
                        setFilters((f) => ({
                          ...f,
                          sma_20_above_50: e.target.checked ? "true" : "",
                        }))
                      }
                      className="rounded border-surface-200"
                    />
                    SMA 20 above SMA 50
                  </label>
                </FilterGroup>

                {/* ADX */}
                <FilterGroup label="ADX (14) — Trend Strength">
                  <input
                    type="number"
                    placeholder="Min ADX"
                    value={filters.min_adx}
                    onChange={(e) =>
                      setFilters((f) => ({ ...f, min_adx: e.target.value }))
                    }
                    className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2"
                  />
                </FilterGroup>

                {/* Bollinger */}
                <FilterGroup label="Bollinger Bands">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={filters.bb_oversold}
                      onChange={(e) =>
                        setFilters((f) => ({
                          ...f,
                          bb_oversold: e.target.checked,
                        }))
                      }
                      className="rounded border-surface-200"
                    />
                    Oversold (%B &lt; 0.2)
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={filters.bb_overbought}
                      onChange={(e) =>
                        setFilters((f) => ({
                          ...f,
                          bb_overbought: e.target.checked,
                        }))
                      }
                      className="rounded border-surface-200"
                    />
                    Overbought (%B &gt; 0.8)
                  </label>
                </FilterGroup>

                {/* Volume */}
                <FilterGroup label="Avg Volume (20d)">
                  <input
                    type="number"
                    placeholder="Min volume"
                    value={filters.min_volume_avg}
                    onChange={(e) =>
                      setFilters((f) => ({
                        ...f,
                        min_volume_avg: e.target.value,
                      }))
                    }
                    className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2"
                  />
                </FilterGroup>

                {/* P/E */}
                <FilterGroup label="P/E Ratio">
                  <div className="flex gap-2">
                    <input
                      type="number"
                      placeholder="Min"
                      value={filters.min_pe}
                      onChange={(e) =>
                        setFilters((f) => ({ ...f, min_pe: e.target.value }))
                      }
                      className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2"
                    />
                    <input
                      type="number"
                      placeholder="Max"
                      value={filters.max_pe}
                      onChange={(e) =>
                        setFilters((f) => ({ ...f, max_pe: e.target.value }))
                      }
                      className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2"
                    />
                  </div>
                </FilterGroup>

                {/* Market Cap */}
                <FilterGroup label="Market Cap">
                  <input
                    type="number"
                    placeholder="Min (USD)"
                    value={filters.min_market_cap}
                    onChange={(e) =>
                      setFilters((f) => ({
                        ...f,
                        min_market_cap: e.target.value,
                      }))
                    }
                    className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2"
                  />
                </FilterGroup>

                {/* Sector */}
                <FilterGroup label="Sector">
                  <input
                    type="text"
                    placeholder="e.g. Technology"
                    value={filters.sector}
                    onChange={(e) =>
                      setFilters((f) => ({ ...f, sector: e.target.value }))
                    }
                    className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2"
                  />
                </FilterGroup>
              </div>
            </Card>
          </div>
        )}

        {/* ── Results ── */}
        <div className={showFilters ? "lg:col-span-3" : "lg:col-span-4"}>
          <Card padding="sm">
            {/* Results header */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-surface-200">
              <div className="flex items-center gap-3">
                <p className="text-sm font-medium text-surface-900">
                  {hasScanned
                    ? `${total} results`
                    : "Run a scan to see results"}
                </p>
                {scanTime > 0 && (
                  <span className="text-xs text-surface-200">{scanTime}ms</span>
                )}
              </div>
            </div>

            {!hasScanned ? (
              <div className="h-64 flex flex-col items-center justify-center text-surface-700">
                <ScanLine className="w-10 h-10 mb-2 text-surface-200" />
                <p>Configure filters and click Run Scan</p>
              </div>
            ) : loading ? (
              <div className="h-64 flex items-center justify-center text-surface-700">
                <div className="animate-pulse">Scanning instruments...</div>
              </div>
            ) : results.length === 0 ? (
              <div className="h-64 flex flex-col items-center justify-center text-surface-700">
                <ScanLine className="w-10 h-10 mb-2 text-surface-200" />
                <p>No instruments match your filters</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-200">
                      <SortHeader
                        field="symbol"
                        label="Symbol"
                        current={sortField}
                        dir={sortDir}
                        onClick={toggleSort}
                      />
                      <th className="text-left py-2 px-2 font-medium text-surface-700">
                        Name
                      </th>
                      <SortHeader
                        field="last_price"
                        label="Price"
                        current={sortField}
                        dir={sortDir}
                        onClick={toggleSort}
                      />
                      <SortHeader
                        field="change_pct"
                        label="Chg%"
                        current={sortField}
                        dir={sortDir}
                        onClick={toggleSort}
                      />
                      <SortHeader
                        field="rsi_14"
                        label="RSI"
                        current={sortField}
                        dir={sortDir}
                        onClick={toggleSort}
                      />
                      <SortHeader
                        field="adx_14"
                        label="ADX"
                        current={sortField}
                        dir={sortDir}
                        onClick={toggleSort}
                      />
                      <SortHeader
                        field="bb_pct_b"
                        label="%B"
                        current={sortField}
                        dir={sortDir}
                        onClick={toggleSort}
                      />
                      <SortHeader
                        field="volume_avg_20d"
                        label="Vol 20d"
                        current={sortField}
                        dir={sortDir}
                        onClick={toggleSort}
                      />
                      <th className="text-left py-2 px-2 font-medium text-surface-700">
                        Trend
                      </th>
                      <SortHeader
                        field="pe_ratio"
                        label="P/E"
                        current={sortField}
                        dir={sortDir}
                        onClick={toggleSort}
                      />
                      <th className="text-right py-2 px-2 font-medium text-surface-700"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((r) => (
                      <tr
                        key={r.instrument_id}
                        className="border-b border-surface-100 hover:bg-surface-50"
                      >
                        <td className="py-2 px-2">
                          <Link
                            href={`/instruments/${r.instrument_id}`}
                            className="font-semibold text-primary-600 hover:text-primary-700"
                          >
                            {r.symbol}
                          </Link>
                        </td>
                        <td className="py-2 px-2 text-surface-900 max-w-[150px] truncate">
                          {r.name}
                        </td>
                        <td className="py-2 px-2 font-mono">
                          {r.last_price?.toFixed(2) ?? "—"}
                        </td>
                        <td
                          className={`py-2 px-2 font-mono ${format.changeColor(r.change_pct ?? 0)}`}
                        >
                          {r.change_pct !== null ? (
                            <span className="flex items-center gap-1">
                              {r.change_pct >= 0 ? (
                                <TrendingUp className="w-3 h-3" />
                              ) : (
                                <TrendingDown className="w-3 h-3" />
                              )}
                              {format.pct(r.change_pct)}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="py-2 px-2 font-mono">
                          <RSICell value={r.rsi_14} />
                        </td>
                        <td className="py-2 px-2 font-mono">
                          {r.adx_14?.toFixed(1) ?? "—"}
                        </td>
                        <td className="py-2 px-2 font-mono">
                          <BBCell value={r.bb_pct_b} />
                        </td>
                        <td className="py-2 px-2 font-mono text-surface-700">
                          {r.volume_avg_20d
                            ? format.compact(r.volume_avg_20d)
                            : "—"}
                        </td>
                        <td className="py-2 px-2">
                          <div className="flex gap-1">
                            {r.above_sma_200 === true && (
                              <span className="px-1.5 py-0.5 text-xs bg-green-50 text-success-600 rounded">
                                ↑200
                              </span>
                            )}
                            {r.above_sma_200 === false && (
                              <span className="px-1.5 py-0.5 text-xs bg-red-50 text-danger-600 rounded">
                                ↓200
                              </span>
                            )}
                            {r.sma_20_above_50 === true && (
                              <span className="px-1.5 py-0.5 text-xs bg-green-50 text-success-600 rounded">
                                20&gt;50
                              </span>
                            )}
                            {r.sma_20_above_50 === false && (
                              <span className="px-1.5 py-0.5 text-xs bg-red-50 text-danger-600 rounded">
                                20&lt;50
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-2 px-2 font-mono text-surface-700">
                          {r.pe_ratio?.toFixed(1) ?? "—"}
                        </td>
                        <td className="py-2 px-2 text-right">
                          <Link
                            href={`/instruments/${r.instrument_id}`}
                            className="text-primary-600 hover:text-primary-700 text-xs font-medium"
                          >
                            Chart →
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

/* ── Sub-components ── */

function FilterGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-surface-700 mb-1.5 uppercase tracking-wide">
        {label}
      </label>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function SortHeader({
  field,
  label,
  current,
  dir,
  onClick,
}: {
  field: SortField;
  label: string;
  current: SortField;
  dir: "asc" | "desc";
  onClick: (f: SortField) => void;
}) {
  const active = current === field;
  return (
    <th
      className="text-left py-2 px-2 font-medium text-surface-700 cursor-pointer select-none hover:text-surface-900"
      onClick={() => onClick(field)}
    >
      <span className="flex items-center gap-1">
        {label}
        {active &&
          (dir === "asc" ? (
            <ChevronUp className="w-3 h-3" />
          ) : (
            <ChevronDown className="w-3 h-3" />
          ))}
      </span>
    </th>
  );
}

function RSICell({ value }: { value: number | null }) {
  if (value === null) return <span>—</span>;
  let color = "text-surface-900";
  if (value < 30) color = "text-success-500 font-medium";
  else if (value > 70) color = "text-danger-500 font-medium";
  return <span className={color}>{value.toFixed(1)}</span>;
}

function BBCell({ value }: { value: number | null }) {
  if (value === null) return <span>—</span>;
  let color = "text-surface-900";
  if (value < 0.2) color = "text-success-500 font-medium";
  else if (value > 0.8) color = "text-danger-500 font-medium";
  return <span className={color}>{value.toFixed(2)}</span>;
}
