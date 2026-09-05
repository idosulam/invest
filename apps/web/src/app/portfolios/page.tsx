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
  Upload,
  FileSpreadsheet,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { ConfirmationModal } from "@/components/ui/ConfirmationModal";
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

/* ── Modal Component ── */

function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-300">
          <h2 className="text-lg font-semibold text-surface-900">{title}</h2>
          <button
            onClick={onClose}
            className="p-1 text-surface-500 hover:text-surface-900 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="px-6 py-4">{children}</div>
      </div>
    </div>
  );
}

/* ── Add Position Modal ── */

function AddPositionModal({
  portfolioId,
  onClose,
  onAdded,
}: {
  portfolioId: string;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [symbol, setSymbol] = useState("");
  const [quantity, setQuantity] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [currentPrice, setCurrentPrice] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!symbol.trim() || !quantity || !avgCost) {
      setError("Symbol, quantity, and avg cost are required");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const token = localStorage.getItem("token");
      const body: Record<string, any> = {
        symbol: symbol.trim().toUpperCase(),
        quantity: parseFloat(quantity),
        avg_cost: parseFloat(avgCost),
      };
      if (currentPrice) body.current_price = parseFloat(currentPrice);

      const res = await fetch(`/api/v1/portfolios/${portfolioId}/add-position`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to add position");
      }
      onAdded();
      onClose();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal title="Add Position" onClose={onClose}>
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-surface-700 mb-1">
            Symbol / Ticker
          </label>
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder="AAPL"
            className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
            autoFocus
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1">
              Quantity
            </label>
            <input
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder="100"
              min="0"
              step="any"
              className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1">
              Avg Cost ($)
            </label>
            <input
              type="number"
              value={avgCost}
              onChange={(e) => setAvgCost(e.target.value)}
              placeholder="185.50"
              min="0"
              step="any"
              className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-surface-700 mb-1">
            Current Price ($){" "}
            <span className="text-surface-400 font-normal">— optional, auto-fetched</span>
          </label>
          <input
            type="number"
            value={currentPrice}
            onChange={(e) => setCurrentPrice(e.target.value)}
            placeholder="Leave empty for live price"
            min="0"
            step="any"
            className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        {error && (
          <p className="text-sm text-danger-600 bg-red-50 rounded-lg px-3 py-2">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-surface-700 hover:text-surface-900"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Plus className="w-4 h-4" />
            )}
            Add Position
          </button>
        </div>
      </div>
    </Modal>
  );
}

/* ── Bulk Import Modal ── */

function BulkImportModal({
  portfolioId,
  onClose,
  onAdded,
}: {
  portfolioId: string;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [rows, setRows] = useState([
    { symbol: "", quantity: "", avg_cost: "" },
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<any>(null);

  const addRow = () => setRows([...rows, { symbol: "", quantity: "", avg_cost: "" }]);
  const removeRow = (i: number) => setRows(rows.filter((_, idx) => idx !== i));
  const updateRow = (i: number, field: string, value: string) => {
    const updated = [...rows];
    (updated[i] as any)[field] = value;
    setRows(updated);
  };

  const handleSubmit = async () => {
    const valid = rows.filter((r) => r.symbol.trim() && r.quantity && r.avg_cost);
    if (valid.length === 0) {
      setError("Add at least one position with symbol, quantity, and avg cost");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/v1/portfolios/${portfolioId}/bulk-import`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          positions: valid.map((r) => ({
            symbol: r.symbol.trim().toUpperCase(),
            quantity: parseFloat(r.quantity),
            avg_cost: parseFloat(r.avg_cost),
          })),
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Import failed");
      }
      const data = await res.json();
      setResult(data);
      if (data.errors === 0) {
        onAdded();
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal title="Bulk Import Positions" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-surface-700">
          Add multiple positions at once. Symbol info and live prices are fetched
          automatically.
        </p>

        <div className="space-y-2">
          {rows.map((row, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                type="text"
                value={row.symbol}
                onChange={(e) => updateRow(i, "symbol", e.target.value)}
                placeholder="AAPL"
                className="flex-1 text-sm border border-surface-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <input
                type="number"
                value={row.quantity}
                onChange={(e) => updateRow(i, "quantity", e.target.value)}
                placeholder="Qty"
                min="0"
                step="any"
                className="w-24 text-sm border border-surface-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <input
                type="number"
                value={row.avg_cost}
                onChange={(e) => updateRow(i, "avg_cost", e.target.value)}
                placeholder="Avg Cost"
                min="0"
                step="any"
                className="w-28 text-sm border border-surface-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              {rows.length > 1 && (
                <button
                  onClick={() => removeRow(i)}
                  className="p-1 text-surface-400 hover:text-danger-600"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          ))}
        </div>

        <button
          onClick={addRow}
          className="text-sm text-primary-600 hover:text-primary-700 font-medium"
        >
          + Add another
        </button>

        {error && (
          <p className="text-sm text-danger-600 bg-red-50 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        {result && (
          <div className="bg-green-50 rounded-lg px-3 py-2 text-sm">
            <p className="text-success-700 font-medium">
              Imported {result.imported} position{result.imported !== 1 ? "s" : ""}
            </p>
            {result.error_details?.length > 0 && (
              <div className="mt-1">
                {result.error_details.map((e: any, i: number) => (
                  <p key={i} className="text-danger-600 text-xs">
                    {e.symbol}: {e.error}
                  </p>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-surface-700 hover:text-surface-900"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Upload className="w-4 h-4" />
            )}
            Import All
          </button>
        </div>
      </div>
    </Modal>
  );
}

/* ── IBKR Import Modal ── */

function IBKRImportModal({
  portfolioId,
  onClose,
  onAdded,
}: {
  portfolioId: string;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [csvData, setCsvData] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<any>(null);

  const handleSubmit = async () => {
    if (!csvData.trim()) {
      setError("Paste your IBKR CSV data");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/v1/portfolios/${portfolioId}/import-ibkr`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ csv_data: csvData }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Import failed");
      }
      const data = await res.json();
      setResult(data);
      if (data.errors === 0) {
        onAdded();
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      setCsvData(ev.target?.result as string);
    };
    reader.readAsText(file);
  };

  return (
    <Modal title="Import from IBKR" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-surface-700">
          Paste your IBKR Activity Statement CSV or upload a file. The importer
          automatically detects the format — both IBKR Activity Statements
          (Open Positions section) and simple CSV (Symbol, Quantity, Cost Basis) work.
        </p>

        <div>
          <label className="block text-sm font-medium text-surface-700 mb-1">
            Upload CSV File
          </label>
          <input
            type="file"
            accept=".csv,.txt"
            onChange={handleFile}
            className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2 file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-sm file:bg-primary-50 file:text-primary-700"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-surface-700 mb-1">
            Or Paste CSV Content
          </label>
          <textarea
            value={csvData}
            onChange={(e) => setCsvData(e.target.value)}
            placeholder={`IBKR Activity Statement format:
Open Positions,Data,Summary,Stocks,USD,AAPL,3,1,328.21,984.63,
Open Positions,Data,Summary,Stocks,USD,NVDA,13.452,1,228.45,3073.11,

Or simple CSV:
Symbol,Quantity,Cost Basis
AAPL,100,185.50`}
            rows={8}
            className="w-full text-sm font-mono border border-surface-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {error && (
          <p className="text-sm text-danger-600 bg-red-50 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        {result && (
          <div className="bg-green-50 rounded-lg px-3 py-2 text-sm">
            <p className="text-success-700 font-medium">
              Imported {result.imported} position{result.imported !== 1 ? "s" : ""}
            </p>
            {result.positions?.length > 0 && (
              <div className="mt-1 space-y-0.5">
                {result.positions.map((p: any, i: number) => (
                  <p key={i} className="text-xs text-surface-700">
                    {p.symbol}: {p.quantity} shares @ ${p.avg_cost}
                    {p.current_price ? ` (now $${p.current_price})` : ""}
                  </p>
                ))}
              </div>
            )}
            {result.error_details?.length > 0 && (
              <div className="mt-1">
                {result.error_details.map((e: any, i: number) => (
                  <p key={i} className="text-danger-600 text-xs">
                    {e.symbol}: {e.error}
                  </p>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-surface-700 hover:text-surface-900"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <FileSpreadsheet className="w-4 h-4" />
            )}
            Import from IBKR
          </button>
        </div>
      </div>
    </Modal>
  );
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

  // Modals
  const [showAddPosition, setShowAddPosition] = useState(false);
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [showIBKRImport, setShowIBKRImport] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [confirmDeleteSymbol, setConfirmDeleteSymbol] = useState<string>("");

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
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchPositions = async (id: string) => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/v1/portfolios/${id}/positions`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) setPositions(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  const fetchAnalytics = async (id: string) => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/v1/portfolios/${id}/analytics`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) setAnalytics(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  const refreshPositions = async () => {
    if (!selectedId) return;
    setRefreshing(true);
    await Promise.all([fetchPositions(selectedId), fetchAnalytics(selectedId)]);
    setRefreshing(false);
  };

  const deletePosition = async (positionId: string) => {
    if (!selectedId) return;
    setDeletingId(positionId);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/v1/portfolios/${selectedId}/positions/${positionId}`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Failed to delete");
      await refreshPositions();
    } catch (e: any) {
      setConfirmDeleteId(null);
      // Error handled silently — modal closes
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  };

  const createPortfolio = async () => {
    if (!newName.trim()) return;
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/v1/portfolios", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ name: newName.trim() }),
      });
      if (res.ok) {
        setNewName("");
        setShowCreate(false);
        fetchPortfolios();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const selectedPortfolio = portfolios.find((p) => p.id === selectedId);

  return (
    <div>
      <Header
        title="Portfolios"
        subtitle="Manage your holdings with live prices"
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-surface-700 border border-surface-300 rounded-lg hover:bg-surface-200"
            >
              <Plus className="w-4 h-4" /> New Portfolio
            </button>
            {selectedId && (
              <>
                <button
                  onClick={() => setShowAddPosition(true)}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700"
                >
                  <Plus className="w-4 h-4" /> Add Position
                </button>
                <button
                  onClick={() => setShowBulkImport(true)}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-purple-600 rounded-lg hover:bg-purple-700"
                >
                  <Upload className="w-4 h-4" /> Bulk Import
                </button>
                <button
                  onClick={() => setShowIBKRImport(true)}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-emerald-600 rounded-lg hover:bg-emerald-700"
                >
                  <FileSpreadsheet className="w-4 h-4" /> Import IBKR
                </button>
                <button
                  onClick={refreshPositions}
                  disabled={refreshing}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-surface-700 border border-surface-300 rounded-lg hover:bg-surface-200 disabled:opacity-50"
                  title="Refresh live prices"
                >
                  <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
                </button>
              </>
            )}
          </div>
        }
      />

      {/* Modals */}
      {showCreate && (
        <Card className="mb-6">
          <div className="flex items-center gap-3">
            <input
              type="text"
              placeholder="Portfolio name..."
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createPortfolio()}
              className="flex-1 text-sm border border-surface-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              autoFocus
            />
            <button
              onClick={createPortfolio}
              className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700"
            >
              Create
            </button>
            <button
              onClick={() => {
                setShowCreate(false);
                setNewName("");
              }}
              className="p-2 text-surface-700 hover:text-surface-900"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </Card>
      )}

      {showAddPosition && selectedId && (
        <AddPositionModal
          portfolioId={selectedId}
          onClose={() => setShowAddPosition(false)}
          onAdded={refreshPositions}
        />
      )}
      {showBulkImport && selectedId && (
        <BulkImportModal
          portfolioId={selectedId}
          onClose={() => setShowBulkImport(false)}
          onAdded={refreshPositions}
        />
      )}
      {showIBKRImport && selectedId && (
        <IBKRImportModal
          portfolioId={selectedId}
          onClose={() => setShowIBKRImport(false)}
          onAdded={refreshPositions}
        />
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
                  <p className="text-lg font-bold text-surface-900 mt-1">
                    {p.name}
                  </p>
                </div>
                <span className="px-2 py-0.5 text-xs bg-amber-50 text-warning-600 rounded-full">
                  {p.type}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Positions */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>
              Positions {selectedPortfolio ? `— ${selectedPortfolio.name}` : ""}
            </CardTitle>
          </CardHeader>

          {loading ? (
            <div className="h-48 flex items-center justify-center text-surface-700">
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading...
            </div>
          ) : positions.length === 0 ? (
            <div className="h-48 flex flex-col items-center justify-center text-surface-700">
              <Briefcase className="w-10 h-10 mb-2 text-surface-400" />
              <p>No positions yet</p>
              <p className="text-sm text-surface-400 mt-1">
                Click "Add Position" or "Import IBKR" to get started
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-300">
                    <th className="text-left py-2 px-3 font-medium text-surface-700">
                      Symbol
                    </th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700">
                      Qty
                    </th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700">
                      Avg Cost
                    </th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700">
                      Current
                    </th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700">
                      P&L
                    </th>
                    <th className="text-right py-2 px-3 font-medium text-surface-700">
                      P&L %
                    </th>
                    <th className="w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((pos) => (
                    <tr
                      key={pos.id}
                      className="border-b border-surface-200 hover:bg-surface-200"
                    >
                      <td className="py-2.5 px-3">
                        <Link
                          href={`/instruments/view?id=${pos.instrument_id}`}
                          className="font-semibold text-primary-600 hover:text-primary-700"
                        >
                          {pos.symbol ?? "?"}
                        </Link>
                        <span className="ml-2 text-surface-700">
                          {pos.instrument_name}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono">
                        {pos.quantity}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono">
                        {format.currency(pos.avg_cost)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono">
                        {pos.current_price
                          ? format.currency(pos.current_price)
                          : "—"}
                      </td>
                      <td
                        className={`py-2.5 px-3 text-right font-mono font-medium ${format.changeColor(pos.unrealized_pnl)}`}
                      >
                        {format.currency(pos.unrealized_pnl)}
                      </td>
                      <td
                        className={`py-2.5 px-3 text-right font-mono ${format.changeColor(pos.unrealized_pnl_pct ?? 0)}`}
                      >
                        {pos.unrealized_pnl_pct !== null
                          ? format.pct(pos.unrealized_pnl_pct)
                          : "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <button
                          onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(pos.id); setConfirmDeleteSymbol(pos.symbol || pos.instrument_name || "this position"); }}
                          className="p-1.5 text-surface-400 hover:text-danger-500 rounded hover:bg-surface-200"
                          title="Delete position"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
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
                <CardHeader>
                  <CardTitle>Summary</CardTitle>
                </CardHeader>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-surface-700">Total Value</span>
                    <span className="font-medium text-surface-900">
                      {format.currency(analytics.total_value)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-surface-700">Total Cost</span>
                    <span className="text-surface-900">
                      {format.currency(analytics.total_cost)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-surface-700">Total P&L</span>
                    <span
                      className={`font-medium ${format.changeColor(analytics.total_pnl)}`}
                    >
                      {format.currency(analytics.total_pnl)} (
                      {format.pct(analytics.total_pnl_pct)})
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-surface-700">Positions</span>
                    <span className="text-surface-900">
                      {analytics.position_count}
                    </span>
                  </div>
                </div>
              </Card>

              {Object.keys(analytics.sector_allocation).length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Sector Allocation</CardTitle>
                  </CardHeader>
                  <div className="space-y-3">
                    {Object.entries(analytics.sector_allocation)
                      .sort((a, b) => b[1] - a[1])
                      .map(([sector, pct]) => (
                        <div key={sector}>
                          <div className="flex justify-between text-sm mb-1">
                            <span className="font-medium text-surface-900">
                              {sector}
                            </span>
                            <span className="text-surface-700">{pct}%</span>
                          </div>
                          <div className="h-2 bg-surface-200 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary-500 rounded-full"
                              style={{ width: `${pct}%` }}
                            />
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

      {/* Delete Confirmation Modal */}
      {confirmDeleteId && (
        <ConfirmationModal
          title="Delete Position"
          message={`Are you sure you want to remove ${confirmDeleteSymbol} from your portfolio? This action cannot be undone.`}
          confirmLabel="Delete Position"
          variant="danger"
          loading={deletingId === confirmDeleteId}
          onConfirm={() => deletePosition(confirmDeleteId)}
          onCancel={() => { setConfirmDeleteId(null); setConfirmDeleteSymbol(""); }}
        />
      )}
    </div>
  );
}
