"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, Plus, Filter, RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";
import { ConfirmationModal } from "@/components/ui/ConfirmationModal";
import { useInstruments } from "@/hooks/useApi";
import type { Instrument } from "@/types";
import { instruments as instrumentsApi } from "@/lib/api";

const TYPES = ["", "STOCK", "ETF", "BENCHMARK", "INDEX"];

export default function InstrumentsPage() {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [page, setPage] = useState(1);
  const [showAddForm, setShowAddForm] = useState(false);
  const [addSymbol, setAddSymbol] = useState("");
  const [addName, setAddName] = useState("");
  const [addType, setAddType] = useState("STOCK");
  const [adding, setAdding] = useState(false);
  const [fetchingData, setFetchingData] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; symbol: string } | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data, isLoading, mutate } = useInstruments({
    page,
    page_size: 50,
    search: search || undefined,
    type: typeFilter || undefined,
  });

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await instrumentsApi.remove(deleteTarget.id);
      mutate();
    } catch (err) {
      // Error handled silently
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
    }
  };

  const instruments: Instrument[] = data?.items ?? [];
  const total: number = data?.total ?? 0;
  const totalPages = Math.ceil(total / 50);

  return (
    <div>
      <Header
        title="Instruments"
        subtitle={`${total} instruments tracked`}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={async () => {
                setRefreshing(true);
                setMessage("");
                try {
                  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
                  const res = await fetch("/api/v1/data/refresh/all", {
                    method: "POST",
                    headers: token ? { Authorization: `Bearer ${token}` } : {},
                  });
                  if (res.ok) {
                    const data = await res.json();
                    setMessage(`Data refreshed: ${data.total_inserted} inserted, ${data.total_updated} updated across ${data.symbols_processed} symbols`);
                    mutate();
                  } else {
                    setMessage("Refresh failed — check server logs");
                  }
                } catch (e) {
                  setMessage("Refresh failed — is the API running?");
                } finally {
                  setRefreshing(false);
                }
              }}
              disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-2 text-[13px] font-medium text-surface-600 bg-surface-200 rounded-lg hover:bg-surface-300 disabled:opacity-50 transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
              {refreshing ? "Refreshing..." : "Refresh Data"}
            </button>
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="flex items-center gap-1.5 px-3.5 py-2 text-[13px] font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Instrument
            </button>
          </div>
        }
      />

      {/* Message */}
      {message && (
        <div className="mb-4 p-3 bg-success-50 border border-success-600/20 rounded-md text-[13px] text-success-400">
          {message}
        </div>
      )}

      {/* Add Form */}
      {showAddForm && (
        <Card className="mb-6">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div>
              <label className="block text-[12px] font-medium text-surface-500 mb-1">Symbol</label>
              <input
                type="text"
                value={addSymbol}
                onChange={(e) => setAddSymbol(e.target.value.toUpperCase())}
                placeholder="AAPL"
                className="w-full"
              />
            </div>
            <div>
              <label className="block text-[12px] font-medium text-surface-500 mb-1">Name</label>
              <input
                type="text"
                value={addName}
                onChange={(e) => setAddName(e.target.value)}
                placeholder="Apple Inc."
                className="w-full"
              />
            </div>
            <div>
              <label className="block text-[12px] font-medium text-surface-500 mb-1">Type</label>
              <select
                value={addType}
                onChange={(e) => setAddType(e.target.value)}
                className="w-full"
              >
                <option value="STOCK">Stock</option>
                <option value="ETF">ETF</option>
                <option value="BENCHMARK">Benchmark</option>
              </select>
            </div>
            <div className="flex items-end">
              <button
                onClick={async () => {
                  if (!addSymbol || !addName) return;
                  setAdding(true);
                  try {
                    const token = localStorage.getItem("token");
                    const res = await fetch("/api/v1/instruments", {
                      method: "POST",
                      headers: {
                        "Content-Type": "application/json",
                        ...(token ? { Authorization: `Bearer ${token}` } : {}),
                      },
                      body: JSON.stringify({
                        symbol: addSymbol,
                        name: addName,
                        type: addType,
                      }),
                    });
                    if (res.ok) {
                      setAddSymbol("");
                      setAddName("");
                      setShowAddForm(false);
                      mutate();
                    }
                  } catch (e) {
                    console.error(e);
                  } finally {
                    setAdding(false);
                  }
                }}
                disabled={adding || !addSymbol || !addName}
                className="px-4 py-2 text-[13px] font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
              >
                {adding ? "Adding..." : "Add"}
              </button>
            </div>
            <div className="flex items-end">
              <button
                onClick={() => setShowAddForm(false)}
                className="px-4 py-2 text-[13px] text-surface-500 border border-surface-300 rounded-lg hover:bg-surface-200 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* ── Filters ── */}
      <Card className="mb-6" padding="sm">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
            <input
              type="text"
              placeholder="Search by symbol or name..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full pl-10 pr-4 py-2"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-surface-400" />
            <select
              value={typeFilter}
              onChange={(e) => {
                setTypeFilter(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2"
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
          <div className="h-64 flex items-center justify-center text-surface-400 text-[13px]">
            Loading...
          </div>
        ) : instruments.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center text-surface-400">
            <Search className="w-8 h-8 mb-2 text-surface-300" />
            <p className="text-[13px] font-medium text-surface-500">No instruments found</p>
            {search && (
              <p className="text-[12px] text-surface-400 mt-1">Try a different search term</p>
            )}
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-surface-300">
                    <th className="text-left py-2 px-3 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Symbol</th>
                    <th className="text-left py-2 px-3 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Name</th>
                    <th className="text-left py-2 px-3 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Type</th>
                    <th className="text-left py-2 px-3 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Exchange</th>
                    <th className="text-left py-2 px-3 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Sector</th>
                    <th className="text-left py-2 px-3 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Currency</th>
                    <th className="text-left py-2 px-3 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Status</th>
                    <th className="text-right py-2 px-3 font-medium text-surface-400 uppercase tracking-wider text-[11px]"></th>
                  </tr>
                </thead>
                <tbody>
                  {instruments.map((inst) => (
                    <tr
                      key={inst.id}
                      className="border-b border-surface-200 hover:bg-surface-200/50 transition-colors"
                    >
                      <td className="py-2.5 px-3">
                        <Link
                          href={`/instruments/view?id=${inst.id}`}
                          className="font-semibold text-primary-400 hover:text-primary-300"
                        >
                          {inst.symbol}
                        </Link>
                      </td>
                      <td className="py-2.5 px-3 text-surface-600 max-w-[200px] truncate">{inst.name}</td>
                      <td className="py-2.5 px-3">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-surface-200 text-surface-500">
                          {inst.type}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-surface-400 font-mono text-[12px]">{inst.exchange ?? "—"}</td>
                      <td className="py-2.5 px-3 text-surface-400 max-w-[150px] truncate">{inst.sector ?? "—"}</td>
                      <td className="py-2.5 px-3 text-surface-400 font-mono text-[12px]">{inst.currency}</td>
                      <td className="py-2.5 px-3">
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
                      <td className="py-2.5 px-3 text-right space-x-3">
                        <Link
                          href={`/instruments/view?id=${inst.id}`}
                          className="text-primary-400 hover:text-primary-300 text-[12px] font-medium"
                        >
                          Open →
                        </Link>
                        <button
                          onClick={() => setDeleteTarget({ id: inst.id, symbol: inst.symbol })}
                          className="text-danger-400 hover:text-danger-500 text-[12px] font-medium"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-surface-300">
                <p className="text-[13px] text-surface-400">
                  Page {page} of {totalPages} · {total} total
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-3 py-1.5 text-[13px] border border-surface-300 rounded-lg hover:bg-surface-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="px-3 py-1.5 text-[13px] border border-surface-300 rounded-lg hover:bg-surface-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <ConfirmationModal
          title="Delete Instrument"
          message={`Delete ${deleteTarget.symbol}? This will also remove all its price data. This action cannot be undone.`}
          confirmLabel="Delete"
          variant="danger"
          loading={deleting}
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
