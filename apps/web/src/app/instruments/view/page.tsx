"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Clock,
  TrendingUp,
  BarChart3,
  Info,
  Layers,
} from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";
import { CandlestickChart } from "@/components/charts/CandlestickChart";
import { useInstrument, useChartData } from "@/hooks/useApi";
import { format } from "@/lib/format";

const TIMEFRAMES = [
  { value: "1D", label: "1D" },
  { value: "1H", label: "1H" },
  { value: "15m", label: "15m" },
  { value: "5m", label: "5m" },
  { value: "1m", label: "1m" },
];

const INDICATOR_PRESETS = [
  { name: "SMA 20/50", indicators: "sma_20,sma_50" },
  { name: "SMA 20/50/200", indicators: "sma_20,sma_50,sma_200" },
  { name: "EMA 12/26", indicators: "ema_12,ema_26" },
  { name: "Bollinger", indicators: "bollinger" },
  { name: "RSI", indicators: "rsi_14" },
  { name: "MACD", indicators: "macd" },
  { name: "ATR", indicators: "atr_14" },
  { name: "ADX", indicators: "adx_14" },
  { name: "Volume (OBV)", indicators: "obv" },
  { name: "VWAP", indicators: "vwap_20" },
];

export default function InstrumentWorkspacePage() {
  const searchParams = useSearchParams();
  const instrumentId = searchParams.get("id") as string;

  const [timeframe, setTimeframe] = useState("1D");
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>([
    "sma_20",
    "sma_50",
  ]);
  const [limit, setLimit] = useState(200);

  const { data: instrument, isLoading: loadingInstrument } =
    useInstrument(instrumentId);
  const { data: chartData, isLoading: loadingChart } = useChartData(
    instrumentId,
    {
      timeframe,
      indicators: selectedIndicators.join(","),
      limit,
    },
  );

  const toggleIndicator = (name: string) => {
    setSelectedIndicators((prev) =>
      prev.includes(name) ? prev.filter((i) => i !== name) : [...prev, name],
    );
  };

  const applyPreset = (preset: string) => {
    setSelectedIndicators(preset.split(","));
  };

  const lastBar = chartData?.bars?.[chartData.bars.length - 1];
  const prevBar = chartData?.bars?.[chartData.bars.length - 2];
  const change =
    lastBar && prevBar
      ? ((lastBar.close - prevBar.close) / prevBar.close) * 100
      : null;

  return (
    <div>
      {/* ── Breadcrumb ── */}
      <div className="flex items-center gap-2 mb-4">
        <Link
          href="/instruments"
          className="text-surface-700 hover:text-surface-900"
        >
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <span className="text-surface-200">/</span>
        <Link
          href="/instruments"
          className="text-sm text-surface-700 hover:text-surface-900"
        >
          Instruments
        </Link>
        <span className="text-surface-200">/</span>
        <span className="text-sm font-medium text-surface-900">
          {instrument?.symbol ?? "..."}
        </span>
      </div>

      {/* ── Instrument Header ── */}
      {loadingInstrument ? (
        <div className="h-16 animate-pulse bg-surface-100 rounded-lg mb-6" />
      ) : instrument ? (
        <Header
          title={`${instrument.symbol} — ${instrument.name}`}
          subtitle={`${instrument.type} · ${instrument.exchange ?? "—"} · ${instrument.currency}`}
          actions={
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                  instrument.status === "ACTIVE"
                    ? "bg-green-50 text-success-600"
                    : "bg-red-50 text-danger-600"
                }`}
              >
                {instrument.status}
              </span>
            </div>
          }
        />
      ) : (
        <div className="text-center py-12 text-surface-700">
          Instrument not found
        </div>
      )}

      {/* ── Price Summary ── */}
      {lastBar && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <Card padding="sm">
            <p className="text-xs text-surface-700 mb-1">Last Price</p>
            <p className="text-xl font-bold text-surface-900">
              {format.currency(lastBar.close)}
            </p>
            {change !== null && (
              <p className={`text-sm ${format.changeColor(change)}`}>
                {format.pct(change)}
              </p>
            )}
          </Card>
          <Card padding="sm">
            <p className="text-xs text-surface-700 mb-1">Open</p>
            <p className="text-lg font-semibold text-surface-900">
              {format.currency(lastBar.open)}
            </p>
          </Card>
          <Card padding="sm">
            <p className="text-xs text-surface-700 mb-1">High</p>
            <p className="text-lg font-semibold text-success-500">
              {format.currency(lastBar.high)}
            </p>
          </Card>
          <Card padding="sm">
            <p className="text-xs text-surface-700 mb-1">Low</p>
            <p className="text-lg font-semibold text-danger-500">
              {format.currency(lastBar.low)}
            </p>
          </Card>
          <Card padding="sm">
            <p className="text-xs text-surface-700 mb-1">Volume</p>
            <p className="text-lg font-semibold text-surface-900">
              {format.compact(lastBar.volume)}
            </p>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* ── Chart (main area) ── */}
        <div className="lg:col-span-3">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-4">
                <CardTitle>Price Chart</CardTitle>
                {/* Timeframe selector */}
                <div className="flex items-center gap-1 bg-surface-100 rounded-lg p-0.5">
                  {TIMEFRAMES.map((tf) => (
                    <button
                      key={tf.value}
                      onClick={() => setTimeframe(tf.value)}
                      className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                        timeframe === tf.value
                          ? "bg-white text-surface-900 shadow-sm"
                          : "text-surface-700 hover:text-surface-900"
                      }`}
                    >
                      {tf.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Limit selector */}
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="text-xs border border-surface-200 rounded-lg px-2 py-1"
              >
                <option value={100}>100 bars</option>
                <option value={200}>200 bars</option>
                <option value={500}>500 bars</option>
                <option value={1000}>1000 bars</option>
              </select>
            </CardHeader>

            {loadingChart ? (
              <div className="h-[400px] flex items-center justify-center text-surface-700">
                <div className="animate-pulse text-center">
                  <BarChart3 className="w-10 h-10 mx-auto mb-2 text-surface-200" />
                  <p>Loading chart data...</p>
                </div>
              </div>
            ) : chartData?.bars?.length ? (
              <CandlestickChart
                bars={chartData.bars}
                indicators={chartData.indicators}
                height={400}
                showVolume={true}
              />
            ) : (
              <div className="h-[400px] flex flex-col items-center justify-center text-surface-700">
                <BarChart3 className="w-10 h-10 mb-2 text-surface-200" />
                <p>No bar data available</p>
                <p className="text-sm text-surface-200 mt-1">
                  Run the data ingestion pipeline to populate bars
                </p>
              </div>
            )}
          </Card>
        </div>

        {/* ── Indicator Panel (sidebar) ── */}
        <div className="space-y-4">
          {/* Presets */}
          <Card>
            <CardHeader>
              <CardTitle>Indicator Presets</CardTitle>
            </CardHeader>
            <div className="space-y-1.5">
              {INDICATOR_PRESETS.map((preset) => {
                const isActive =
                  selectedIndicators.join(",") === preset.indicators;
                return (
                  <button
                    key={preset.name}
                    onClick={() => applyPreset(preset.indicators)}
                    className={`w-full text-left px-3 py-2 text-sm rounded-lg transition-colors ${
                      isActive
                        ? "bg-primary-50 text-primary-700 font-medium"
                        : "text-surface-700 hover:bg-surface-50"
                    }`}
                  >
                    {preset.name}
                  </button>
                );
              })}
            </div>
          </Card>

          {/* Individual indicators */}
          <Card>
            <CardHeader>
              <CardTitle>Indicators</CardTitle>
            </CardHeader>
            <div className="space-y-1">
              {[
                "sma_20",
                "sma_50",
                "sma_200",
                "ema_12",
                "ema_26",
                "rsi_14",
                "macd",
                "bollinger",
                "atr_14",
                "adx_14",
                "obv",
                "vwap_20",
              ].map((name) => (
                <label
                  key={name}
                  className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedIndicators.includes(name)}
                    onChange={() => toggleIndicator(name)}
                    className="rounded border-surface-200 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="text-sm text-surface-900 font-mono">
                    {name}
                  </span>
                </label>
              ))}
            </div>
          </Card>

          {/* Instrument Info */}
          {instrument && (
            <Card>
              <CardHeader>
                <CardTitle>Details</CardTitle>
              </CardHeader>
              <div className="space-y-2 text-sm">
                {instrument.sector && (
                  <div className="flex justify-between">
                    <span className="text-surface-700">Sector</span>
                    <span className="text-surface-900">
                      {instrument.sector}
                    </span>
                  </div>
                )}
                {instrument.industry && (
                  <div className="flex justify-between">
                    <span className="text-surface-700">Industry</span>
                    <span className="text-surface-900">
                      {instrument.industry}
                    </span>
                  </div>
                )}
                {instrument.country && (
                  <div className="flex justify-between">
                    <span className="text-surface-700">Country</span>
                    <span className="text-surface-900">
                      {instrument.country}
                    </span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-surface-700">Currency</span>
                  <span className="text-surface-900">
                    {instrument.currency}
                  </span>
                </div>
                {instrument.isin && (
                  <div className="flex justify-between">
                    <span className="text-surface-700">ISIN</span>
                    <span className="text-surface-900 font-mono text-xs">
                      {instrument.isin}
                    </span>
                  </div>
                )}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
