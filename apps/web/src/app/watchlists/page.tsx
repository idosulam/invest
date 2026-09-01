"use client";

import { useState } from "react";
import Link from "next/link";
import { ListOrdered, Plus, Trash2, Eye, X, Search } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";
import { useWatchlists, useInstruments } from "@/hooks/useApi";
import { watchlists as watchlistsApi } from "@/lib/api";
import type { WatchlistDetail, Instrument } from "@/types";

export default function WatchlistsPage() {
  const { data, isLoading, mutate } = useWatchlists();
  const watchlists: any[] = data?.items ?? [];

  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<WatchlistDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [showAddInstrument, setShowAddInstrument] = useState(false);

  const createWatchlist = async () => {
    if (!newName.trim()) return;
    try {
      await watchlistsApi.create(newName.trim());
      setNewName("");
      setCreating(false);
      mutate();
    } catch (e) {
      console.error(e);
    }
  };

  const deleteWatchlist = async (id: string) => {
    if (!confirm("Delete this watchlist?")) return;
    try {
      await watchlistsApi.delete(id);
      if (selectedId === id) {
        setSelectedId(null);
        setDetail(null);
      }
      mutate();
    } catch (e) {
      console.error(e);
    }
  };

  const loadDetail = async (id: string) => {
    setSelectedId(id);
    setLoadingDetail(true);
    try {
      const d = await watchlistsApi.get(id);
      setDetail(d);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingDetail(false);
    }
  };

  const removeInstrument = async (instrumentId: string) => {
    if (!selectedId) return;
    try {
      await watchlistsApi.removeInstrument(selectedId, instrumentId);
      loadDetail(selectedId);
      mutate();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div>
      <Header
        title="Watchlists"
        subtitle="Track instruments you care about"
        actions={
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700"
          >
            <Plus className="w-4 h-4" /> New Watchlist
          </button>
        }
      />

      {/* Create modal */}
      {creating && (
        <Card className="mb-6">
          <div className="flex items-center gap-3">
            <input
              type="text"
              placeholder="Watchlist name..."
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createWatchlist()}
              className="flex-1 text-sm border border-surface-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              autoFocus
            />
            <button
              onClick={createWatchlist}
              className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700"
            >
              Create
            </button>
            <button
              onClick={() => {
                setCreating(false);
                setNewName("");
              }}
              className="p-2 text-surface-700 hover:text-surface-900"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Watchlist list */}
        <Card>
          <CardHeader>
            <CardTitle>Your Watchlists</CardTitle>
          </CardHeader>

          {isLoading ? (
            <div className="h-48 flex items-center justify-center text-surface-700">
              Loading...
            </div>
          ) : watchlists.length === 0 ? (
            <div className="h-48 flex flex-col items-center justify-center text-surface-700">
              <ListOrdered className="w-10 h-10 mb-2 text-surface-200" />
              <p>No watchlists yet</p>
            </div>
          ) : (
            <div className="space-y-2">
              {watchlists.map((wl) => (
                <div
                  key={wl.id}
                  onClick={() => loadDetail(wl.id)}
                  className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
                    selectedId === wl.id
                      ? "bg-primary-50 border border-primary-200"
                      : "bg-surface-50 hover:bg-surface-100"
                  }`}
                >
                  <div>
                    <p className="font-medium text-surface-900">{wl.name}</p>
                    <p className="text-xs text-surface-700">
                      {wl.instrument_ids.length} instrument
                      {wl.instrument_ids.length !== 1 ? "s" : ""}
                    </p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteWatchlist(wl.id);
                    }}
                    className="p-1.5 text-surface-200 hover:text-danger-500 rounded"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Watchlist detail */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>{detail?.name ?? "Select a watchlist"}</CardTitle>
              {selectedId && (
                <button
                  onClick={() => setShowAddInstrument(true)}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm border border-surface-200 rounded-lg hover:bg-surface-50"
                >
                  <Plus className="w-3 h-3" /> Add
                </button>
              )}
            </CardHeader>

            {!selectedId ? (
              <div className="h-64 flex flex-col items-center justify-center text-surface-700">
                <Eye className="w-10 h-10 mb-2 text-surface-200" />
                <p>Select a watchlist to view instruments</p>
              </div>
            ) : loadingDetail ? (
              <div className="h-64 flex items-center justify-center text-surface-700">
                Loading...
              </div>
            ) : detail?.instruments.length === 0 ? (
              <div className="h-64 flex flex-col items-center justify-center text-surface-700">
                <ListOrdered className="w-10 h-10 mb-2 text-surface-200" />
                <p>No instruments in this watchlist</p>
                <p className="text-sm text-surface-200 mt-1">
                  Click + Add to add instruments
                </p>
              </div>
            ) : (
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
                        Status
                      </th>
                      <th className="text-right py-2 px-3 font-medium text-surface-700"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail?.instruments.map((inst) => (
                      <tr
                        key={inst.id}
                        className="border-b border-surface-100 hover:bg-surface-50"
                      >
                        <td className="py-2.5 px-3">
                          <Link
                            href={`/instruments/view?id=${inst.id}`}
                            className="font-semibold text-primary-600 hover:text-primary-700"
                          >
                            {" "}
                            {inst.symbol}
                          </Link>
                        </td>
                        <td className="py-2.5 px-3 text-surface-900">
                          {inst.name}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className="px-2 py-0.5 text-xs bg-surface-100 text-surface-700 rounded-full">
                            {inst.type}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-surface-700">
                          {inst.exchange ?? "—"}
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 text-xs rounded-full ${
                              inst.status === "ACTIVE"
                                ? "bg-green-50 text-success-600"
                                : "bg-red-50 text-danger-600"
                            }`}
                          >
                            {inst.status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Link
                              href={`/instruments/view?id=${inst.id}`}
                              className="text-primary-600 hover:text-primary-700 text-xs font-medium"
                            >
                              Chart →
                            </Link>
                            <button
                              onClick={() => removeInstrument(inst.id)}
                              className="p-1 text-surface-200 hover:text-danger-500"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* Add instrument modal */}
      {showAddInstrument && selectedId && (
        <AddInstrumentModal
          watchlistId={selectedId}
          onClose={() => setShowAddInstrument(false)}
          onAdded={() => {
            loadDetail(selectedId);
            mutate();
          }}
        />
      )}
    </div>
  );
}

/* ── Add Instrument Modal ── */

function AddInstrumentModal({
  watchlistId,
  onClose,
  onAdded,
}: {
  watchlistId: string;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [search, setSearch] = useState("");
  const { data } = useInstruments({
    search: search || undefined,
    page_size: 20,
  });
  const instruments: Instrument[] = data?.items ?? [];

  const add = async (instrumentId: string) => {
    try {
      await watchlistsApi.addInstrument(watchlistId, instrumentId);
      onAdded();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <Card className="w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
        <CardHeader>
          <CardTitle>Add Instrument</CardTitle>
          <button
            onClick={onClose}
            className="p-1 text-surface-700 hover:text-surface-900"
          >
            <X className="w-4 h-4" />
          </button>
        </CardHeader>

        <div className="mb-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-200" />
            <input
              type="text"
              placeholder="Search by symbol or name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 text-sm border border-surface-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              autoFocus
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto space-y-1">
          {instruments.map((inst) => (
            <div
              key={inst.id}
              className="flex items-center justify-between p-2 rounded-lg hover:bg-surface-50"
            >
              <div>
                <span className="font-semibold text-surface-900">
                  {inst.symbol}
                </span>
                <span className="ml-2 text-sm text-surface-700">
                  {inst.name}
                </span>
              </div>
              <button
                onClick={() => add(inst.id)}
                className="px-3 py-1 text-xs font-medium text-primary-600 border border-primary-200 rounded-lg hover:bg-primary-50"
              >
                Add
              </button>
            </div>
          ))}
          {search && instruments.length === 0 && (
            <p className="text-center text-sm text-surface-700 py-4">
              No instruments found
            </p>
          )}
        </div>
      </Card>
    </div>
  );
}
