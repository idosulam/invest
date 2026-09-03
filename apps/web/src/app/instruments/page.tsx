"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, Plus, Filter, RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";
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

  const { data, isLoading, mutate } = useInstruments({
    page,
    page_size: 50,
    search: search || undefined,
    type: typeFilter || undefined,
  });

  const handleDelete = async (id: string, symbol: string) => {
    if (
      !confirm(`Delete ${symbol}? This will also remove all its price data.`)
    ) {
      return;
    }
    try {
      await instrumentsApi.remove(id);
      mutate(); // refresh the list
    } catch (err) {
      alert("Failed to delete instrument. You may need admin permissions.");
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
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-surface-700 bg-surface-100 rounded-lg hover:bg-surface-200 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
              {refreshing ? "Refreshing..." : "Refresh Data"}
            </button>
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700"
            >
              <Plus className="w-4 h-4" />
              Add Instrument
            </button>
          </div>
        }
      />

      {/* Message */}
      {message && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-success-600">
          {message}
        </div>
      )}

      {/* Add Form */}
      {showAddForm && (
        <Card className="mb-6">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div>
              <label className="block text-xs font-medium text-surface-700 mb-1">
                Symbol
              </label>
              <input
                type="text"
                value={addSymbol}
                onChange={(e) => setAddSymbol(e.target.value.toUpperCase())}
                placeholder="AAPL"
                className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-700 mb-1">
                Name
              </label>
              <input
                type="text"
                value={addName}
                onChange={(e) => setAddName(e.target.value)}
                placeholder="Apple Inc."
                className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-700 mb-1">
                Type
              </label>
              <select
                value={addType}
                onChange={(e) => setAddType(e.target.value)}
                className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2"
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
                className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                {adding ? "Adding..." : "Add"}
              </button>
            </div>
            <div className="flex items-end">
              <button
                onClick={() => setShowAddForm(false)}
                className="px-4 py-2 text-sm text-surface-700 border border-surface-200 rounded-lg hover:bg-surface-50"
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
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-200" />
            <input
              type="text"
              placeholder="Search by symbol or name..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full pl-10 pr-4 py-2 text-sm border border-surface-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-surface-200" />
            <select
              value={typeFilter}
              onChange={(e) => {
                setTypeFilter(e.target.value);
                setPage(1);
              }}
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
              <p className="text-sm text-surface-200 mt-1">
                Try a different search term
              </p>
            )}
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-200">
                    <th className="text-left py-2 px-3 font-medium text-surface-700">
                      Symbol
                    </th>
                    <th className="text-left py-2 px-3 font-medium text-surface-700">
                      Name
                    </th>
                    <th className="text-left py-2 px-3 font-medium text-surface-700">
                      Type
                    </th>
                    <th className="text-left py-2 px-3 font-medium text-surface-700">
                      Exchange
                    </th>
                    <th className="text-left py-2 px-3 font-medium text-surface-700">
                      Sector
                    </th>
                    <th className="text-left py-2 px-3 font-medium text-surface-700">
                      Currency
                    </th>
                    <th className="text-left py-2 px-3 font-medium text-surface-700">
                      Status
                    </th>
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
                          href={`/instruments/view?id=${inst.id}`}
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
                      <td className="py-2.5 px-3 text-surface-700">
                        {inst.exchange ?? "—"}
                      </td>
                      <td className="py-2.5 px-3 text-surface-700 max-w-[150px] truncate">
                        {inst.sector ?? "—"}
                      </td>
                      <td className="py-2.5 px-3 text-surface-700">
                        {inst.currency}
                      </td>
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
                      <td className="py-2.5 px-3 text-right space-x-3">
                        <Link
                          href={`/instruments/view?id=${inst.id}`}
                          className="text-primary-600 hover:text-primary-700 text-xs font-medium"
                        >
                          Open →
                        </Link>
                        <button
                          onClick={() => handleDelete(inst.id, inst.symbol)}
                          className="text-danger-600 hover:text-danger-700 text-xs font-medium"
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
