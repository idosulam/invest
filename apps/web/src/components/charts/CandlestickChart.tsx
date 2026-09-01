"use client";

import { useMemo } from "react";
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Area,
} from "recharts";
import { format } from "@/lib/format";
import type { BarPoint } from "@/types";

interface ChartDataPoint extends BarPoint {
  // Computed fields for rendering
  bodyBottom: number;
  bodyHeight: number;
  wickTop: number;
  wickBottom: number;
  color: string;
}

interface IndicatorData {
  [key: string]: (number | null)[];
}

interface CandlestickChartProps {
  bars: BarPoint[];
  indicators?: IndicatorData;
  height?: number;
  showVolume?: boolean;
}

function prepareData(bars: BarPoint[]): ChartDataPoint[] {
  return bars.map((bar) => {
    const isUp = bar.close >= bar.open;
    return {
      ...bar,
      bodyBottom: Math.min(bar.open, bar.close),
      bodyHeight: Math.abs(bar.close - bar.open),
      wickTop: bar.high,
      wickBottom: bar.low,
      color: isUp ? "#22c55e" : "#ef4444",
    };
  });
}

function mergeIndicators(
  data: ChartDataPoint[],
  indicators: IndicatorData
): Record<string, any>[] {
  return data.map((point, i) => {
    const row: Record<string, any> = { ...point };
    for (const [key, values] of Object.entries(indicators)) {
      if (Array.isArray(values)) {
        row[key] = values[i] ?? null;
      } else if (typeof values === "object" && values !== null) {
        // Nested indicator (e.g., macd, bollinger)
        for (const [subKey, subValues] of Object.entries(values)) {
          if (Array.isArray(subValues)) {
            row[`${key}_${subKey}`] = subValues[i] ?? null;
          }
        }
      }
    }
    return row;
  });
}

const INDICATOR_COLORS: Record<string, string> = {
  sma_20: "#3b82f6",
  sma_50: "#f59e0b",
  sma_200: "#ef4444",
  ema_12: "#8b5cf6",
  ema_26: "#06b6d4",
  rsi_14: "#f59e0b",
  atr_14: "#6366f1",
  adx_14: "#ec4899",
  vwap_20: "#14b8a6",
  obv: "#8b5cf6",
  macd_macd: "#3b82f6",
  macd_signal: "#ef4444",
  macd_histogram: "#22c55e",
  bollinger_upper: "#94a3b8",
  bollinger_middle: "#3b82f6",
  bollinger_lower: "#94a3b8",
};

export function CandlestickChart({
  bars,
  indicators,
  height = 400,
  showVolume = true,
}: CandlestickChartProps) {
  const chartData = useMemo(() => {
    const prepared = prepareData(bars);
    if (indicators) return mergeIndicators(prepared, indicators);
    return prepared;
  }, [bars, indicators]);

  const indicatorKeys = useMemo(() => {
    if (!indicators) return [];
    const keys: string[] = [];
    for (const [key, values] of Object.entries(indicators)) {
      if (Array.isArray(values)) {
        keys.push(key);
      } else if (typeof values === "object" && values !== null) {
        for (const subKey of Object.keys(values)) {
          keys.push(`${key}_${subKey}`);
        }
      }
    }
    return keys;
  }, [indicators]);

  // Separate overlay indicators (on price chart) from sub-chart indicators
  const overlayKeys = indicatorKeys.filter(
    (k) => !["rsi_14", "atr_14", "adx_14", "obv", "macd_macd", "macd_signal", "macd_histogram"].includes(k)
  );
  const subChartKeys = indicatorKeys.filter((k) =>
    ["rsi_14", "atr_14", "adx_14", "obv"].includes(k)
  );
  const hasMACD = indicatorKeys.some((k) => k.startsWith("macd_"));

  const formatDate = (ts: string) => {
    const d = new Date(ts);
    return format.shortDate(d);
  };

  const formatPrice = (v: number) => v.toFixed(2);

  return (
    <div className="space-y-2">
      {/* Main price chart */}
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="ts"
            tickFormatter={formatDate}
            tick={{ fontSize: 11, fill: "#64748b" }}
            stroke="#cbd5e1"
          />
          <YAxis
            domain={["auto", "auto"]}
            tickFormatter={formatPrice}
            tick={{ fontSize: 11, fill: "#64748b" }}
            stroke="#cbd5e1"
            width={70}
          />
          <Tooltip
            content={<ChartTooltip />}
            labelFormatter={formatDate}
          />
          <Legend />

          {/* Candlestick bodies as bars */}
          <Bar
            dataKey="bodyBottom"
            fill="transparent"
            stroke="transparent"
            legendHidden
          />

          {/* High-Low range as area (simulates wicks) */}
          <Area
            dataKey="high"
            fill="none"
            stroke="transparent"
            legendHidden
          />

          {/* Close line as the main price visualization */}
          <Line
            type="monotone"
            dataKey="close"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            name="Close"
          />

          {/* Overlay indicators */}
          {overlayKeys.map((key) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={INDICATOR_COLORS[key] || "#94a3b8"}
              strokeWidth={1.5}
              dot={false}
              name={key}
              connectNulls={false}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Volume chart */}
      {showVolume && (
        <ResponsiveContainer width="100%" height={80}>
          <ComposedChart data={chartData} margin={{ top: 0, right: 5, left: 5, bottom: 5 }}>
            <XAxis dataKey="ts" tickFormatter={formatDate} tick={{ fontSize: 10, fill: "#94a3b8" }} stroke="#e2e8f0" />
            <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} stroke="#e2e8f0" width={70} />
            <Bar dataKey="volume" fill="#94a3b8" opacity={0.5} name="Volume" />
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* Sub-chart indicators (RSI, ATR, ADX) */}
      {subChartKeys.map((key) => (
        <div key={key}>
          <p className="text-xs font-medium text-surface-700 mb-1 uppercase">{key.replace("_", " ")}</p>
          <ResponsiveContainer width="100%" height={80}>
            <ComposedChart data={chartData} margin={{ top: 0, right: 5, left: 5, bottom: 5 }}>
              <XAxis dataKey="ts" tickFormatter={formatDate} tick={{ fontSize: 10, fill: "#94a3b8" }} stroke="#e2e8f0" />
              <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} stroke="#e2e8f0" width={70} />
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <Line
                type="monotone"
                dataKey={key}
                stroke={INDICATOR_COLORS[key] || "#6366f1"}
                strokeWidth={1.5}
                dot={false}
                name={key}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      ))}

      {/* MACD sub-chart */}
      {hasMACD && (
        <div>
          <p className="text-xs font-medium text-surface-700 mb-1 uppercase">MACD</p>
          <ResponsiveContainer width="100%" height={100}>
            <ComposedChart data={chartData} margin={{ top: 0, right: 5, left: 5, bottom: 5 }}>
              <XAxis dataKey="ts" tickFormatter={formatDate} tick={{ fontSize: 10, fill: "#94a3b8" }} stroke="#e2e8f0" />
              <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} stroke="#e2e8f0" width={70} />
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <Line type="monotone" dataKey="macd_macd" stroke="#3b82f6" strokeWidth={1.5} dot={false} name="MACD" />
              <Line type="monotone" dataKey="macd_signal" stroke="#ef4444" strokeWidth={1.5} dot={false} name="Signal" />
              <Bar dataKey="macd_histogram" fill="#22c55e" opacity={0.6} name="Histogram" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      ))}
    </div>
  );
}

/* ── Custom Tooltip ── */

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;

  const data = payload[0]?.payload;
  if (!data) return null;

  return (
    <div className="bg-surface-900 text-white text-xs rounded-lg px-3 py-2 shadow-lg">
      <p className="text-surface-200 mb-1">{formatDate(data.ts)}</p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
        <span className="text-surface-200">Open</span>
        <span className="text-right font-mono">{data.open?.toFixed(2)}</span>
        <span className="text-surface-200">High</span>
        <span className="text-right font-mono">{data.high?.toFixed(2)}</span>
        <span className="text-surface-200">Low</span>
        <span className="text-right font-mono">{data.low?.toFixed(2)}</span>
        <span className="text-surface-200">Close</span>
        <span className="text-right font-mono font-medium">{data.close?.toFixed(2)}</span>
        <span className="text-surface-200">Volume</span>
        <span className="text-right font-mono">{format.compact(data.volume)}</span>
      </div>
    </div>
  );
}

function formatDate(ts: string) {
  return format.shortDate(new Date(ts));
}
