"use client";

import { useState } from "react";
import { Compass, TrendingUp, TrendingDown, Plus, Loader2, Check } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
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
      alert(`Failed to add ${result.symbol}. It may already exist.`);
    } finally {
      setAddingSymbol(null);
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
                  : "bg-surface-100 text-surface-700 hover:bg-surface-200"
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
                <tr className="border-b border-surface-200 text-left">
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
                    <tr key={r.symbol} className="border-b border-surface-100 hover:bg-surface-50">
                      <td className="py-2.5 px-3 font-semibold text-primary-600">{r.symbol}</td>
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
                        {alreadyAdded ? (
                          <span className="inline-flex items-center gap-1 text-xs text-surface-500">
                            <Check className="w-3.5 h-3.5" /> Tracked
                          </span>
                        ) : (
                          <button
                            onClick={() => handleAdd(r)}
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
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
