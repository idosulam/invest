"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Briefcase,
  Plus,
  TrendingUp,
  TrendingDown,
  Loader2,
  X,
  Search,
} from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";
import { format } from "@/lib/format";

/* ── Types ── */

interface Portfolio {
  id: string;
  name: string;
  owner_id: string;
  base_currency: string;
  type: string;
  created_at: string;
}

interface Position {
  id: string;
  instrument_id: string;
  symbol: string | null;
  instrument_name: string | null;
  quantity: number;
  avg_cost: number;
  current_price: number | null;
  market_value: number | null;
  unrealized_pnl: number;
  unrealized_pnl_pct: number | null;
  realized_pnl: number;
}

interface Analytics {
  total_value: number;
  total_cost: number;
  total_pnl: number;
  total_pnl_pct: number;
  position_count: number;
  sector_allocation: Record<string, number>;
  top_positions: { symbol: string; value: number; pnl: number }[];
}

/* ── Page ── */

export default function PortfoliosPage() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");

  useEffect(() => {
    fetchPortfolios();
  }, []);

  useEffect(() => {
    if (selectedId) {
      fetchPositions(selectedId);
      fetchAnalytics(selectedId);
    }
  }, [selectedId]);

  const fetchPortfolios = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/v1/portfolios", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setPortfolios(data);
        if (data.length > 0) setSelectedId(data[0].id);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const fetchPositions = async (id: string) => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/v1/portfolios/${id}/positions`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) setPositions(await res.json());
    } catch (e) { console.error(e); }
  };

  const fetchAnalytics = async (id: string) => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/v1/portfolios/${id}/analytics`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) setAnalytics(await res.json());
    } catch (e) { console.error(e); }
  };

  const createPortfolio = async () => {
    if (!newName.trim()) return;
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/v1/portfolios", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ name: newName.trim() }),
      });
      if (res.ok) {
        setNewName("");
        setShowCreate(false);
        fetchPortfolios();
      }
    } catch (e) { console.error(e); }
  };

  const selectedPortfolio = portfolios.find((p) => p.id === selectedId);

  return (
    <div>
      <Header
        title="Portfolios"
        subtitle="Paper trading portfolios and analytics"
        actions={
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700"
          >
            <Plus className="w-4 h-4" /> New Portfolio
          </button>
        }
      />

      {showCreate && (
        <Card className="mb-6">
          <div className="flex items-center gap-3">
            <input
              type="text"
              placeholder="Portfolio name..."
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createPortfolio()}
              className="flex-1 text-sm border border-surface-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              autoFocus
            />
            <button onClick={createPortfolio} className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700">Create</button>
            <button onClick={() => { setShowCreate(false); setNewName(""); }} className="p-2 text-surface-700 hover:text-surface-900"><X className="w-4 h-4" /></button>
          </div>
        </Card>
      )}

      {/* Portfolio cards */}
      {portfolios.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          {portfolios.map((p) => (
            <Card
              key={p.id}
              className={`cursor-pointer transition-colors ${selectedId === p.id ? "ring-2 ring-primary-500" : ""}`}
              onClick={() => setSelectedId(p.id)}
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-surface-700">{p.type}</p>
                  <p className="text-lg font-bold text-surface-900 mt-1">{p.name}</p>
                </div>
                <span className="px-2 py-0.5 text-xs bg-amber-50 text-warning-600 rounded-full">{p.type}</span>
              </div>
            </Card>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Positions */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Positions {selectedPortfolio ? `— ${selectedPortfolio.name}` : ""}</CardTitle>
          </CardHeader>

          {loading ? (
            <div className="h-48 flex items-center justify-center text-surface-700"><Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading...</div>
          ) : positions.length === 0 ? (
            <div className="h-48 flex flex-col items-center justify-center text-surface-700">
              <Briefcase className="w-10 h-10 mb-2 text-surface-200" />
              <p>No positions yet</p>
              <p className="text-sm text-surface-200 mt-1">Execute paper trades via the API</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-200">
                    <th className="text-left py-2 px-3 font-medium text-surface-700">Symbol</th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700">Qty</th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700">Avg Cost</th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700">Current</th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700">P&L</th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700">P&L %</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((pos) => (
                    <tr key={pos.id} className="border-b border-surface-100 hover:bg-surface-50">
                      <td className="py-2.5 px-3">
                        <Link href={`/instruments/${pos.instrument_id}`} className="font-semibold text-primary-600 hover:text-primary-700">{pos.symbol ?? "?"}</Link>
                        <span className="ml-2 text-surface-700">{pos.instrument_name}</span>
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono">{pos.quantity}</td>
                      <td className="py-2.5 px-3 text-right font-mono">{format.currency(pos.avg_cost)}</td>
                      <td className="py-2.5 px-3 text-right font-mono">{pos.current_price ? format.currency(pos.current_price) : "—"}</td>
                      <td className={`py-2.5 px-3 text-right font-mono font-medium ${format.changeColor(pos.unrealized_pnl)}`}>{format.currency(pos.unrealized_pnl)}</td>
                      <td className={`py-2.5 px-3 text-right font-mono ${format.changeColor(pos.unrealized_pnl_pct ?? 0)}`}>{pos.unrealized_pnl_pct !== null ? format.pct(pos.unrealized_pnl_pct) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Analytics sidebar */}
        <div className="space-y-4">
          {analytics && (
            <>
              <Card>
                <CardHeader><CardTitle>Summary</CardTitle></CardHeader>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-surface-700">Total Value</span>
                    <span className="font-medium text-surface-900">{format.currency(analytics.total_value)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-surface-700">Total Cost</span>
                    <span className="text-surface-900">{format.currency(analytics.total_cost)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-surface-700">Total P&L</span>
                    <span className={`font-medium ${format.changeColor(analytics.total_pnl)}`}>{format.currency(analytics.total_pnl)} ({format.pct(analytics.total_pnl_pct)})</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-surface-700">Positions</span>
                    <span className="text-surface-900">{analytics.position_count}</span>
                  </div>
                </div>
              </Card>

              {Object.keys(analytics.sector_allocation).length > 0 && (
                <Card>
                  <CardHeader><CardTitle>Sector Allocation</CardTitle></CardHeader>
                  <div className="space-y-3">
                    {Object.entries(analytics.sector_allocation).sort((a, b) => b[1] - a[1]).map(([sector, pct]) => (
                      <div key={sector}>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="font-medium text-surface-900">{sector}</span>
                          <span className="text-surface-700">{pct}%</span>
                        </div>
                        <div className="h-2 bg-surface-100 rounded-full overflow-hidden">
                          <div className="h-full bg-primary-500 rounded-full" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
