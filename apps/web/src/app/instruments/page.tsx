"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, Plus, Filter } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";
import { useInstruments } from "@/hooks/useApi";
import type { Instrument } from "@/types";

const TYPES = ["", "STOCK", "ETF", "BENCHMARK", "INDEX"];

export default function InstrumentsPage() {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useInstruments({
    page,
    page_size: 50,
    search: search || undefined,
    type: typeFilter || undefined,
  });

  const instruments: Instrument[] = data?.items ?? [];
  const total: number = data?.total ?? 0;
  const totalPages = Math.ceil(total / 50);

  return (
    <div>
      <Header
        title="Instruments"
        subtitle={`${total} instruments tracked`}
      />

      {/* ── Filters ── */}
      <Card className="mb-6" padding="sm">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-200" />
            <input
              type="text"
              placeholder="Search by symbol or name..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="w-full pl-10 pr-4 py-2 text-sm border border-surface-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-surface-200" />
            <select
              value={typeFilter}
              onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
              className="text-sm border border-surface-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">All Types</option>
              <option value="STOCK">Stock</option>
              <option value="ETF">ETF</option>
              <option value="BENCHMARK">Benchmark</option>
              <option value="INDEX">Index</option>
            </select>
          </div>
        </div>
      </Card>

      {/* ── Table ── */}
      <Card padding="sm">
        {isLoading ? (
          <div className="h-64 flex items-center justify-center text-surface-700">
            Loading...
          </div>
        ) : instruments.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center text-surface-700">
            <Search className="w-10 h-10 mb-2 text-surface-200" />
            <p>No instruments found</p>
            {search && (
              <p className="text-sm text-surface-200 mt-1">Try a different search term</p>
            )}
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-200">
                    <th className="text-left py-2 px-3 font-medium text-surface-700">Symbol</th>
                    <th className="text-left py-2 px-3 font-medium text-surface-700">Name</th>
                    <th className="text-left py-2 px-3 font-medium text-surface-700">Type</th>
                    <th className="text-left py-2 px-3 font-medium text-surface-700">Exchange</th>
                    <th className="text-left py-2 px-3 font-medium text-surface-700">Sector</th>
                    <th className="text-left py-2 px-3 font-medium text-surface-700">Currency</th>
                    <th className="text-left py-2 px-3 font-medium text-surface-700">Status</th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700"></th>
                  </tr>
                </thead>
                <tbody>
                  {instruments.map((inst) => (
                    <tr
                      key={inst.id}
                      className="border-b border-surface-100 hover:bg-surface-50 transition-colors"
                    >
                      <td className="py-2.5 px-3">
                        <Link
                          href={`/instruments/${inst.id}`}
                          className="font-semibold text-primary-600 hover:text-primary-700"
                        >
                          {inst.symbol}
                        </Link>
                      </td>
                      <td className="py-2.5 px-3 text-surface-900 max-w-[200px] truncate">
                        {inst.name}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-surface-100 text-surface-700">
                          {inst.type}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-surface-700">{inst.exchange ?? "—"}</td>
                      <td className="py-2.5 px-3 text-surface-700 max-w-[150px] truncate">
                        {inst.sector ?? "—"}
                      </td>
                      <td className="py-2.5 px-3 text-surface-700">{inst.currency}</td>
                      <td className="py-2.5 px-3">
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
                      <td className="py-2.5 px-3 text-right">
                        <Link
                          href={`/instruments/${inst.id}`}
                          className="text-primary-600 hover:text-primary-700 text-xs font-medium"
                        >
                          Open →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-surface-200">
                <p className="text-sm text-surface-700">
                  Page {page} of {totalPages} · {total} total
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-3 py-1.5 text-sm border border-surface-200 rounded-lg hover:bg-surface-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="px-3 py-1.5 text-sm border border-surface-200 rounded-lg hover:bg-surface-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
