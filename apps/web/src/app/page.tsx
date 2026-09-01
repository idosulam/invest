"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  AlertTriangle,
  BarChart3,
  Eye,
  ArrowRight,
} from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";
import { useInstruments, useWatchlists } from "@/hooks/useApi";
import { format } from "@/lib/format";
import type { Instrument, Watchlist } from "@/types";

/* ── Stat Card ── */

function StatCard({
  label,
  value,
  change,
  icon: Icon,
  color = "primary",
}: {
  label: string;
  value: string;
  change?: number;
  icon: any;
  color?: string;
}) {
  const colorMap: Record<string, string> = {
    primary: "bg-primary-50 text-primary-600",
    success: "bg-green-50 text-success-600",
    warning: "bg-amber-50 text-warning-600",
    danger: "bg-red-50 text-danger-600",
  };

  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-surface-700 mb-1">{label}</p>
          <p className="text-2xl font-bold text-surface-900">{value}</p>
          {change !== undefined && (
            <p className={`text-sm mt-1 flex items-center gap-1 ${format.changeColor(change)}`}>
              {change >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              {format.pct(change)}
            </p>
          )}
        </div>
        <div className={`p-3 rounded-lg ${colorMap[color]}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </Card>
  );
}

/* ── Main Dashboard ── */

export default function DashboardPage() {
  const { data: instrumentsData, isLoading: loadingInstruments } = useInstruments({ page_size: 10 });
  const { data: watchlistData, isLoading: loadingWatchlists } = useWatchlists();

  const instruments: Instrument[] = instrumentsData?.items ?? [];
  const watchlists: Watchlist[] = watchlistData?.items ?? [];

  return (
    <div>
      <Header
        title="Dashboard"
        subtitle="Market overview and portfolio summary"
      />

      {/* ── Stats Row ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="Tracked Instruments"
          value={String(instrumentsData?.total ?? 0)}
          icon={BarChart3}
          color="primary"
        />
        <StatCard
          label="Watchlists"
          value={String(watchlists.length)}
          icon={Eye}
          color="success"
        />
        <StatCard
          label="Active Signals"
          value="—"
          icon={Activity}
          color="warning"
        />
        <StatCard
          label="Data Quality"
          value="OK"
          icon={AlertTriangle}
          color="success"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Instruments Table ── */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Instruments</CardTitle>
            <Link
              href="/instruments"
              className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
            >
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </CardHeader>

          {loadingInstruments ? (
            <div className="h-48 flex items-center justify-center text-surface-700">
              Loading instruments...
            </div>
          ) : instruments.length === 0 ? (
            <div className="h-48 flex flex-col items-center justify-center text-surface-700">
              <BarChart3 className="w-10 h-10 mb-2 text-surface-200" />
              <p>No instruments yet</p>
              <p className="text-sm text-surface-200 mt-1">
                Add instruments via the API or data ingestion pipeline
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-200">
                    <th className="text-left py-2 px-2 font-medium text-surface-700">Symbol</th>
                    <th className="text-left py-2 px-2 font-medium text-surface-700">Name</th>
                    <th className="text-left py-2 px-2 font-medium text-surface-700">Type</th>
                    <th className="text-left py-2 px-2 font-medium text-surface-700">Exchange</th>
                    <th className="text-left py-2 px-2 font-medium text-surface-700">Status</th>
                    <th className="text-right py-2 px-2 font-medium text-surface-700"></th>
                  </tr>
                </thead>
                <tbody>
                  {instruments.map((inst) => (
                    <tr
                      key={inst.id}
                      className="border-b border-surface-100 hover:bg-surface-50 transition-colors"
                    >
                      <td className="py-2.5 px-2">
                        <Link
                          href={`/instruments/${inst.id}`}
                          className="font-semibold text-primary-600 hover:text-primary-700"
                        >
                          {inst.symbol}
                        </Link>
                      </td>
                      <td className="py-2.5 px-2 text-surface-900">{inst.name}</td>
                      <td className="py-2.5 px-2">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-surface-100 text-surface-700">
                          {inst.type}
                        </span>
                      </td>
                      <td className="py-2.5 px-2 text-surface-700">{inst.exchange ?? "—"}</td>
                      <td className="py-2.5 px-2">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                            inst.status === "ACTIVE"
                              ? "bg-green-50 text-success-600"
                              : inst.status === "DELISTED"
                              ? "bg-red-50 text-danger-600"
                              : "bg-amber-50 text-warning-600"
                          }`}
                        >
                          {inst.status}
                        </span>
                      </td>
                      <td className="py-2.5 px-2 text-right">
                        <Link
                          href={`/instruments/${inst.id}`}
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

        {/* ── Watchlists ── */}
        <Card>
          <CardHeader>
            <CardTitle>Watchlists</CardTitle>
          </CardHeader>

          {loadingWatchlists ? (
            <div className="h-48 flex items-center justify-center text-surface-700">
              Loading...
            </div>
          ) : watchlists.length === 0 ? (
            <div className="h-48 flex flex-col items-center justify-center text-surface-700">
              <Eye className="w-10 h-10 mb-2 text-surface-200" />
              <p>No watchlists yet</p>
              <p className="text-sm text-surface-200 mt-1">Create one to track instruments</p>
            </div>
          ) : (
            <div className="space-y-3">
              {watchlists.map((wl) => (
                <div
                  key={wl.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-surface-50 hover:bg-surface-100 transition-colors"
                >
                  <div>
                    <p className="font-medium text-surface-900">{wl.name}</p>
                    <p className="text-xs text-surface-700">
                      {wl.instrument_ids.length} instrument{wl.instrument_ids.length !== 1 ? "s" : ""}
                    </p>
                  </div>
                  <Eye className="w-4 h-4 text-surface-200" />
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* ── Market Status Banner ── */}
      <Card className="mt-6" padding="sm">
        <div className="flex items-center gap-3 px-2">
          <div className="w-2 h-2 rounded-full bg-success-500 animate-pulse" />
          <p className="text-sm text-surface-700">
            <span className="font-medium text-surface-900">System Status:</span>{" "}
            All services operational · Data pipeline running · Research mode active
          </p>
        </div>
      </Card>
    </div>
  );
}
