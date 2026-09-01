"use client";

import { useState } from "react";
import {
  Briefcase,
  Plus,
  TrendingUp,
  TrendingDown,
  PieChart,
  ArrowRightLeft,
} from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";
import { format } from "@/lib/format";

/* ── Demo data ── */

const DEMO_PORTFOLIOS = [
  { id: "1", name: "Paper Trading #1", type: "PAPER", currency: "USD", positions: 5, total_value: 125340, pnl: 3240, pnl_pct: 2.65 },
  { id: "2", name: "Swing Strategy Test", type: "PAPER", currency: "USD", positions: 3, total_value: 50120, pnl: -870, pnl_pct: -1.71 },
];

const DEMO_POSITIONS = [
  { symbol: "AAPL", name: "Apple Inc.", qty: 50, avg_cost: 178.50, current: 192.30, pnl: 690, pnl_pct: 7.73 },
  { symbol: "MSFT", name: "Microsoft Corp.", qty: 30, avg_cost: 380.00, current: 415.20, pnl: 1056, pnl_pct: 9.26 },
  { symbol: "GOOGL", name: "Alphabet Inc.", qty: 40, avg_cost: 140.00, current: 155.80, pnl: 632, pnl_pct: 11.29 },
  { symbol: "NVDA", name: "NVIDIA Corp.", qty: 20, avg_cost: 480.00, current: 450.00, pnl: -600, pnl_pct: -6.25 },
  { symbol: "TSLA", name: "Tesla Inc.", qty: 25, avg_cost: 220.00, current: 245.50, pnl: 637.5, pnl_pct: 11.59 },
];

export default function PortfoliosPage() {
  const [selectedPortfolio, setSelectedPortfolio] = useState("1");

  return (
    <div>
      <Header
        title="Portfolios"
        subtitle="Paper trading portfolios and analytics"
        actions={
          <button className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700">
            <Plus className="w-4 h-4" /> New Portfolio
          </button>
        }
      />

      {/* Portfolio cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {DEMO_PORTFOLIOS.map((p) => (
          <Card
            key={p.id}
            className={`cursor-pointer transition-colors ${
              selectedPortfolio === p.id ? "ring-2 ring-primary-500" : ""
            }`}
            onClick={() => setSelectedPortfolio(p.id)}
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-surface-700">{p.type}</p>
                <p className="text-lg font-bold text-surface-900 mt-1">{p.name}</p>
                <p className="text-sm text-surface-700 mt-0.5">{p.positions} positions</p>
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold text-surface-900">{format.currency(p.total_value)}</p>
                <p className={`text-sm flex items-center justify-end gap-1 ${format.changeColor(p.pnl)}`}>
                  {p.pnl >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                  {format.pct(p.pnl_pct)} ({format.currency(p.pnl)})
                </p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Positions table */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Positions — Paper Trading #1</CardTitle>
          </CardHeader>

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
                {DEMO_POSITIONS.map((pos) => (
                  <tr key={pos.symbol} className="border-b border-surface-100 hover:bg-surface-50">
                    <td className="py-2.5 px-3">
                      <span className="font-semibold text-surface-900">{pos.symbol}</span>
                      <span className="ml-2 text-surface-700">{pos.name}</span>
                    </td>
                    <td className="py-2.5 px-3 text-right font-mono">{pos.qty}</td>
                    <td className="py-2.5 px-3 text-right font-mono">{format.currency(pos.avg_cost)}</td>
                    <td className="py-2.5 px-3 text-right font-mono">{format.currency(pos.current)}</td>
                    <td className={`py-2.5 px-3 text-right font-mono font-medium ${format.changeColor(pos.pnl)}`}>
                      {format.currency(pos.pnl)}
                    </td>
                    <td className={`py-2.5 px-3 text-right font-mono ${format.changeColor(pos.pnl_pct)}`}>
                      {format.pct(pos.pnl_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Allocation sidebar */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Allocation</CardTitle>
            </CardHeader>
            <div className="space-y-3">
              {DEMO_POSITIONS.map((pos) => {
                const value = pos.qty * pos.current;
                const total = DEMO_POSITIONS.reduce((s, p) => s + p.qty * p.current, 0);
                const pct = (value / total) * 100;
                return (
                  <div key={pos.symbol}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="font-medium text-surface-900">{pos.symbol}</span>
                      <span className="text-surface-700">{pct.toFixed(1)}%</span>
                    </div>
                    <div className="h-2 bg-surface-100 rounded-full overflow-hidden">
                      <div className="h-full bg-primary-500 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Summary</CardTitle>
            </CardHeader>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-surface-700">Total Value</span>
                <span className="font-medium text-surface-900">{format.currency(125340)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-surface-700">Total P&L</span>
                <span className="font-medium text-success-500">{format.currency(3240)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-surface-700">Positions</span>
                <span className="text-surface-900">5</span>
              </div>
              <div className="flex justify-between">
                <span className="text-surface-700">Type</span>
                <span className="px-2 py-0.5 text-xs bg-amber-50 text-warning-600 rounded-full">Paper</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
