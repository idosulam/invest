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
  accent = "primary",
}: {
  label: string;
  value: string;
  change?: number;
  icon: any;
  accent?: "primary" | "success" | "warning" | "danger";
}) {
  const accentMap: Record<string, string> = {
    primary: "text-primary-400",
    success: "text-success-400",
    warning: "text-warning-400",
    danger: "text-danger-400",
  };

  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[12px] font-medium text-surface-400 uppercase tracking-wider mb-1">{label}</p>
          <p className="text-2xl font-bold text-surface-800 tabular-nums">{value}</p>
          {change !== undefined && (
            <p className={`text-[13px] mt-1 flex items-center gap-1 ${format.changeColor(change)}`}>
              {change >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              {format.pct(change)}
            </p>
          )}
        </div>
        <Icon className={`w-5 h-5 ${accentMap[accent]}`} />
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
          accent="primary"
        />
        <StatCard
          label="Watchlists"
          value={String(watchlists.length)}
          icon={Eye}
          accent="success"
        />
        <StatCard
          label="Active Signals"
          value="—"
          icon={Activity}
          accent="warning"
        />
        <StatCard
          label="Data Quality"
          value="OK"
          icon={AlertTriangle}
          accent="success"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Instruments Table ── */}
        <Card className="lg:col-span-2" padding="sm">
          <CardHeader className="px-4 pt-3">
            <CardTitle>Instruments</CardTitle>
            <Link
              href="/instruments"
              className="text-[13px] text-primary-400 hover:text-primary-300 flex items-center gap-1 font-medium"
            >
              View all <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </CardHeader>

          {loadingInstruments ? (
            <div className="h-48 flex items-center justify-center text-surface-400 text-[13px]">
              Loading instruments...
            </div>
          ) : instruments.length === 0 ? (
            <div className="h-48 flex flex-col items-center justify-center text-surface-400">
              <BarChart3 className="w-8 h-8 mb-2 text-surface-300" />
              <p className="text-[13px] font-medium text-surface-500">No instruments yet</p>
              <p className="text-[12px] text-surface-400 mt-1">
                Add instruments via the API or data ingestion pipeline
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-surface-300">
                    <th className="text-left py-2 px-4 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Symbol</th>
                    <th className="text-left py-2 px-4 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Name</th>
                    <th className="text-left py-2 px-4 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Type</th>
                    <th className="text-left py-2 px-4 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Exchange</th>
                    <th className="text-left py-2 px-4 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Status</th>
                    <th className="text-right py-2 px-4 font-medium text-surface-400 uppercase tracking-wider text-[11px]"></th>
                  </tr>
                </thead>
                <tbody>
                  {instruments.map((inst) => (
                    <tr
                      key={inst.id}
                      className="border-b border-surface-200 hover:bg-surface-200/50 transition-colors cursor-pointer"
                      onClick={() => window.location.href = `/instruments/view?id=${inst.id}`}
                    >
                      <td className="py-2.5 px-4">
                        <Link
                          href={`/instruments/view?id=${inst.id}`}
                          className="font-semibold text-primary-400 hover:text-primary-300"
                        >
                          {inst.symbol}
                        </Link>
                      </td>
                      <td className="py-2.5 px-4 text-surface-600">{inst.name}</td>
                      <td className="py-2.5 px-4">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-surface-200 text-surface-500">
                          {inst.type}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-surface-400 font-mono text-[12px]">{inst.exchange ?? "—"}</td>
                      <td className="py-2.5 px-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${
                            inst.status === "ACTIVE"
                              ? "bg-success-50 text-success-400"
                              : inst.status === "DELISTED"
                              ? "bg-danger-50 text-danger-400"
                              : "bg-warning-50 text-warning-400"
                          }`}
                        >
                          {inst.status}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-right">
                        <Link
                          href={`/instruments/view?id=${inst.id}`}
                          className="text-primary-400 hover:text-primary-300 text-[12px] font-medium"
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
            <div className="h-48 flex items-center justify-center text-surface-400 text-[13px]">
              Loading...
            </div>
          ) : watchlists.length === 0 ? (
            <div className="h-48 flex flex-col items-center justify-center text-surface-400">
              <Eye className="w-8 h-8 mb-2 text-surface-300" />
              <p className="text-[13px] font-medium text-surface-500">No watchlists yet</p>
              <p className="text-[12px] text-surface-400 mt-1">Create one to track instruments</p>
            </div>
          ) : (
            <div className="space-y-2">
              {watchlists.map((wl) => (
                <Link
                  key={wl.id}
                  href="/watchlists"
                  className="flex items-center justify-between p-3 rounded-lg bg-surface-200/50 hover:bg-surface-200 transition-colors cursor-pointer"
                >
                  <div>
                    <p className="text-[13px] font-medium text-surface-700">{wl.name}</p>
                    <p className="text-[11px] text-surface-400">
                      {wl.instrument_ids.length} instrument{wl.instrument_ids.length !== 1 ? "s" : ""}
                    </p>
                  </div>
                  <Eye className="w-4 h-4 text-surface-400" />
                </Link>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* ── Market Status Banner ── */}
      <Card className="mt-6" padding="sm">
        <div className="flex items-center gap-3 px-2">
          <div className="w-1.5 h-1.5 rounded-full bg-success-400 animate-pulse" />
          <p className="text-[13px] text-surface-500">
            <span className="font-medium text-surface-600">System Status</span>
            <span className="text-surface-300 mx-2">·</span>
            All services operational
            <span className="text-surface-300 mx-2">·</span>
            Data pipeline running
            <span className="text-surface-300 mx-2">·</span>
            Research mode active
          </p>
        </div>
      </Card>
    </div>
  );
}
