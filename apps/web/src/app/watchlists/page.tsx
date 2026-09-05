"use client";

import { useState } from "react";
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
            className="flex items-center gap-1.5 px-3.5 py-2 text-[13px] font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" /> New Watchlist
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
              className="flex-1"
              autoFocus
            />
            <button
              onClick={createWatchlist}
              className="px-4 py-2 text-[13px] font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
            >
              Create
            </button>
            <button
              onClick={() => { setCreating(false); setNewName(""); }}
              className="p-2 text-surface-400 hover:text-surface-600"
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
            <div className="h-48 flex items-center justify-center text-surface-400 text-[13px]">Loading...</div>
          ) : watchlists.length === 0 ? (
            <div className="h-48 flex flex-col items-center justify-center text-surface-400">
              <ListOrdered className="w-8 h-8 mb-2 text-surface-300" />
              <p className="text-[13px] font-medium text-surface-500">No watchlists yet</p>
            </div>
          ) : (
            <div className="space-y-2">
              {watchlists.map((wl) => (
                <div
                  key={wl.id}
                  onClick={() => loadDetail(wl.id)}
                  className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
                    selectedId === wl.id
                      ? "bg-primary-500/10 border border-primary-500/30"
                      : "bg-surface-200/50 hover:bg-surface-200"
                  }`}
                >
                  <div>
                    <p className="text-[13px] font-medium text-surface-700">{wl.name}</p>
                    <p className="text-[11px] text-surface-400">
                      {wl.instrument_ids.length} instrument{wl.instrument_ids.length !== 1 ? "s" : ""}
                    </p>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteWatchlist(wl.id); }}
                    className="p-1.5 text-surface-400 hover:text-danger-400 rounded transition-colors"
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
                  className="flex items-center gap-1 px-3 py-1.5 text-[13px] font-medium border border-surface-300 rounded-lg hover:bg-surface-200 text-surface-500 transition-colors"
                >
                  <Plus className="w-3 h-3" /> Add
                </button>
              )}
            </CardHeader>

            {!selectedId ? (
              <div className="h-64 flex flex-col items-center justify-center text-surface-400">
                <Eye className="w-8 h-8 mb-2 text-surface-300" />
                <p className="text-[13px] font-medium text-surface-500">Select a watchlist to view instruments</p>
              </div>
            ) : loadingDetail ? (
              <div className="h-64 flex items-center justify-center text-surface-400 text-[13px]">Loading...</div>
            ) : detail?.instruments.length === 0 ? (
              <div className="h-64 flex flex-col items-center justify-center text-surface-400">
                <ListOrdered className="w-8 h-8 mb-2 text-surface-300" />
                <p className="text-[13px] font-medium text-surface-500">No instruments in this watchlist</p>
                <p className="text-[12px] text-surface-400 mt-1">Click + Add to add instruments</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="border-b border-surface-300">
                      <th className="text-left py-2 px-3 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Symbol</th>
                      <th className="text-left py-2 px-3 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Name</th>
                      <th className="text-left py-2 px-3 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Type</th>
                      <th className="text-left py-2 px-3 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Exchange</th>
                      <th className="text-left py-2 px-3 font-medium text-surface-400 uppercase tracking-wider text-[11px]">Status</th>
                      <th className="text-right py-2 px-3 font-medium text-surface-400 uppercase tracking-wider text-[11px]"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail?.instruments.map((inst) => {
                      const href = `/instruments/view?id=${inst.id}`;
                      return (
                      <tr key={inst.id} className="border-b border-surface-200 hover:bg-surface-200/50 transition-colors cursor-pointer" onClick={() => window.location.href = href}>
                        <td className="py-2.5 px-3">
                          <span className="font-semibold text-primary-400">{inst.symbol}</span>
                        </td>
                        <td className="py-2.5 px-3 text-surface-600">{inst.name}</td>
                        <td className="py-2.5 px-3">
                          <span className="px-2 py-0.5 text-[11px] font-medium bg-surface-200 text-surface-500 rounded">{inst.type}</span>
                        </td>
                        <td className="py-2.5 px-3 text-surface-400 font-mono text-[12px]">{inst.exchange ?? "—"}</td>
                        <td className="py-2.5 px-3">
                          <span className={`px-2 py-0.5 text-[11px] font-medium rounded ${
                            inst.status === "ACTIVE" ? "bg-success-50 text-success-400" : "bg-danger-50 text-danger-400"
                          }`}>{inst.status}</span>
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <span className="text-primary-400 text-[12px] font-medium">Chart →</span>
                            <button onClick={(e) => { e.stopPropagation(); removeInstrument(inst.id); }} className="p-1 text-surface-400 hover:text-danger-400">
                              <X className="w-3 h-3" />
                            </button>
                          </div>
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
      </div>

      {/* Add instrument modal */}
      {showAddInstrument && selectedId && (
        <AddInstrumentModal
          watchlistId={selectedId}
          onClose={() => setShowAddInstrument(false)}
          onAdded={() => { loadDetail(selectedId); mutate(); }}
        />
      )}
    </div>
  );
}

function AddInstrumentModal({
  watchlistId, onClose, onAdded,
}: {
  watchlistId: string; onClose: () => void; onAdded: () => void;
}) {
  const [search, setSearch] = useState("");
  const { data } = useInstruments({ search: search || undefined, page_size: 20 });
  const instruments: Instrument[] = data?.items ?? [];

  const add = async (instrumentId: string) => {
    try { await watchlistsApi.addInstrument(watchlistId, instrumentId); onAdded(); }
    catch (e) { console.error(e); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <Card className="w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
        <CardHeader>
          <CardTitle>Add Instrument</CardTitle>
          <button onClick={onClose} className="p-1 text-surface-400 hover:text-surface-600"><X className="w-4 h-4" /></button>
        </CardHeader>
        <div className="mb-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
            <input type="text" placeholder="Search by symbol or name..." value={search} onChange={(e) => setSearch(e.target.value)} className="w-full pl-10 pr-4 py-2" autoFocus />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto space-y-1">
          {instruments.map((inst) => (
            <div key={inst.id} className="flex items-center justify-between p-2 rounded-lg hover:bg-surface-200 transition-colors">
              <div>
                <span className="text-[13px] font-semibold text-surface-700">{inst.symbol}</span>
                <span className="ml-2 text-[13px] text-surface-400">{inst.name}</span>
              </div>
              <button onClick={() => add(inst.id)} className="px-3 py-1 text-[12px] font-medium text-primary-400 border border-primary-500/30 rounded hover:bg-primary-500/10 transition-colors">
                Add
              </button>
            </div>
          ))}
          {search && instruments.length === 0 && (
            <p className="text-center text-[13px] text-surface-400 py-4">No instruments found</p>
          )}
        </div>
      </Card>
    </div>
  );
}
