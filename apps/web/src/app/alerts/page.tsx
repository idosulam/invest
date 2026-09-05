"use client";

import { useState, useEffect } from "react";
import {
  Bell,
  Plus,
  Mail,
  Webhook,
  Smartphone,
  X,
  ToggleLeft,
  ToggleRight,
  Clock,
  Loader2,
  Trash2,
} from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";

/* ── Types ── */

interface AlertRule {
  id: string;
  owner_id: string;
  name: string;
  conditions: Record<string, any>;
  channels: string[];
  cooldown_minutes: number;
  enabled: boolean;
  last_fired_at: string | null;
  created_at: string;
}

const CHANNEL_ICONS: Record<string, any> = { EMAIL: Mail, WEBHOOK: Webhook, IN_APP: Smartphone };

/* ── Page ── */

export default function AlertsPage() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCondition, setNewCondition] = useState('{"type": "rsi_below", "threshold": 30}');

  useEffect(() => { fetchRules(); }, []);

  const fetchRules = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/v1/alerts", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) setRules(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const createRule = async () => {
    if (!newName.trim()) return;
    try {
      const token = localStorage.getItem("token");
      let conditions = {};
      try { conditions = JSON.parse(newCondition); } catch { return; }
      const res = await fetch("/api/v1/alerts", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ name: newName.trim(), conditions, channels: ["IN_APP"] }),
      });
      if (res.ok) {
        setNewName("");
        setShowCreate(false);
        fetchRules();
      }
    } catch (e) { console.error(e); }
  };

  const toggleRule = async (id: string, enabled: boolean) => {
    try {
      const token = localStorage.getItem("token");
      await fetch(`/api/v1/alerts/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ enabled: !enabled }),
      });
      fetchRules();
    } catch (e) { console.error(e); }
  };

  const deleteRule = async (id: string) => {
    if (!confirm("Delete this alert rule?")) return;
    try {
      const token = localStorage.getItem("token");
      await fetch(`/api/v1/alerts/${id}`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      fetchRules();
    } catch (e) { console.error(e); }
  };

  return (
    <div>
      <Header
        title="Alerts"
        subtitle="Configure alert rules and notification channels"
        actions={
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700"
          >
            <Plus className="w-4 h-4" /> New Alert Rule
          </button>
        }
      />

      {showCreate && (
        <Card className="mb-6">
          <div className="space-y-3">
            <input
              type="text"
              placeholder="Alert name..."
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              autoFocus
            />
            <textarea
              placeholder='Conditions JSON, e.g. {"type": "rsi_below", "threshold": 30}'
              value={newCondition}
              onChange={(e) => setNewCondition(e.target.value)}
              className="w-full text-sm font-mono border border-surface-300 rounded-lg px-3 py-2 h-20 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <div className="flex gap-2">
              <button onClick={createRule} className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700">Create</button>
              <button onClick={() => { setShowCreate(false); setNewName(""); }} className="px-4 py-2 text-sm border border-surface-300 rounded-lg hover:bg-surface-200">Cancel</button>
            </div>
          </div>
        </Card>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card padding="sm">
          <p className="text-xs text-surface-700 mb-1">Total Rules</p>
          <p className="text-2xl font-bold text-surface-900">{rules.length}</p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-surface-700 mb-1">Active</p>
          <p className="text-2xl font-bold text-success-500">{rules.filter((r) => r.enabled).length}</p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-surface-700 mb-1">Disabled</p>
          <p className="text-2xl font-bold text-surface-400">{rules.filter((r) => !r.enabled).length}</p>
        </Card>
      </div>

      {/* Rules list */}
      <Card>
        <CardHeader><CardTitle>Alert Rules</CardTitle></CardHeader>

        {loading ? (
          <div className="h-48 flex items-center justify-center text-surface-700"><Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading...</div>
        ) : rules.length === 0 ? (
          <div className="h-48 flex flex-col items-center justify-center text-surface-700">
            <Bell className="w-10 h-10 mb-2 text-surface-400" />
            <p className="font-medium">No alert rules yet</p>
            <p className="text-sm text-surface-400 mt-1">Create one to get notified</p>
          </div>
        ) : (
          <div className="space-y-3">
            {rules.map((rule) => (
              <div key={rule.id} className={`p-4 rounded-lg border transition-colors ${rule.enabled ? "bg-white border-surface-300" : "bg-surface-200 border-surface-200 opacity-60"}`}>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="font-medium text-surface-900">{rule.name}</h4>
                      {!rule.enabled && <span className="px-2 py-0.5 text-xs bg-surface-200 text-surface-700 rounded-full">Disabled</span>}
                    </div>
                    <div className="flex items-center gap-4 mt-2 text-sm">
                      <code className="font-mono text-xs text-surface-900 bg-surface-200 px-2 py-1 rounded">{JSON.stringify(rule.conditions)}</code>
                    </div>
                    <div className="flex items-center gap-3 mt-2">
                      <div className="flex items-center gap-1.5">
                        {rule.channels.map((ch) => {
                          const Icon = CHANNEL_ICONS[ch] || Bell;
                          return <span key={ch} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-surface-200 text-surface-700 rounded-full"><Icon className="w-3 h-3" />{ch}</span>;
                        })}
                      </div>
                      <span className="flex items-center gap-1 text-xs text-surface-400"><Clock className="w-3 h-3" />{rule.cooldown_minutes}m cooldown</span>
                      {rule.last_fired_at && <span className="text-xs text-surface-400">Last: {new Date(rule.last_fired_at).toLocaleDateString()}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <button onClick={() => toggleRule(rule.id, rule.enabled)}>
                      {rule.enabled ? <ToggleRight className="w-8 h-8 text-primary-600" /> : <ToggleLeft className="w-8 h-8 text-surface-400" />}
                    </button>
                    <button onClick={() => deleteRule(rule.id)} className="p-1.5 text-surface-400 hover:text-danger-500 rounded"><Trash2 className="w-4 h-4" /></button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
