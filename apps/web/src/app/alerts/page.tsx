"use client";

import { useState } from "react";
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
} from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";

/* ── Demo data ── */

const DEMO_ALERTS = [
  { id: "1", name: "RSI Oversold — AAPL", condition: "RSI(14) < 30", instrument: "AAPL", channels: ["IN_APP", "EMAIL"], enabled: true, lastFired: "2024-12-10T14:30:00Z", cooldown: 60 },
  { id: "2", name: "Price Crosses SMA 200 — MSFT", condition: "Close crosses SMA(200)", instrument: "MSFT", channels: ["IN_APP"], enabled: true, lastFired: null, cooldown: 120 },
  { id: "3", name: "Volume Spike — NVDA", condition: "Volume > 3x 20d avg", instrument: "NVDA", channels: ["IN_APP", "WEBHOOK"], enabled: false, lastFired: "2024-12-08T09:45:00Z", cooldown: 30 },
  { id: "4", name: "Bollinger Squeeze — TSLA", condition: "BB Bandwidth < 0.05", instrument: "TSLA", channels: ["IN_APP", "EMAIL"], enabled: true, lastFired: null, cooldown: 60 },
];

const CHANNEL_ICONS: Record<string, any> = {
  EMAIL: Mail,
  WEBHOOK: Webhook,
  IN_APP: Smartphone,
};

export default function AlertsPage() {
  const [alerts, setAlerts] = useState(DEMO_ALERTS);

  const toggleAlert = (id: string) => {
    setAlerts((prev) =>
      prev.map((a) => (a.id === id ? { ...a, enabled: !a.enabled } : a))
    );
  };

  return (
    <div>
      <Header
        title="Alerts"
        subtitle="Configure alert rules and notification channels"
        actions={
          <button className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700">
            <Plus className="w-4 h-4" /> New Alert Rule
          </button>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card padding="sm">
          <p className="text-xs text-surface-700 mb-1">Total Rules</p>
          <p className="text-2xl font-bold text-surface-900">{alerts.length}</p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-surface-700 mb-1">Active</p>
          <p className="text-2xl font-bold text-success-500">{alerts.filter((a) => a.enabled).length}</p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-surface-700 mb-1">Fired Today</p>
          <p className="text-2xl font-bold text-warning-500">1</p>
        </Card>
      </div>

      {/* Alert rules */}
      <Card>
        <CardHeader>
          <CardTitle>Alert Rules</CardTitle>
        </CardHeader>

        <div className="space-y-3">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={`p-4 rounded-lg border transition-colors ${
                alert.enabled
                  ? "bg-white border-surface-200"
                  : "bg-surface-50 border-surface-100 opacity-60"
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h4 className="font-medium text-surface-900">{alert.name}</h4>
                    {!alert.enabled && (
                      <span className="px-2 py-0.5 text-xs bg-surface-100 text-surface-700 rounded-full">
                        Disabled
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-4 mt-2 text-sm">
                    <div>
                      <span className="text-surface-700">Condition: </span>
                      <code className="font-mono text-surface-900 bg-surface-100 px-1.5 py-0.5 rounded">
                        {alert.condition}
                      </code>
                    </div>
                    <div>
                      <span className="text-surface-700">Instrument: </span>
                      <span className="font-medium text-surface-900">{alert.instrument}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 mt-2">
                    {/* Channels */}
                    <div className="flex items-center gap-1.5">
                      {alert.channels.map((ch) => {
                        const Icon = CHANNEL_ICONS[ch] || Bell;
                        return (
                          <span
                            key={ch}
                            className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-surface-100 text-surface-700 rounded-full"
                          >
                            <Icon className="w-3 h-3" />
                            {ch}
                          </span>
                        );
                      })}
                    </div>

                    {/* Cooldown */}
                    <span className="flex items-center gap-1 text-xs text-surface-200">
                      <Clock className="w-3 h-3" />
                      {alert.cooldown}m cooldown
                    </span>

                    {/* Last fired */}
                    {alert.lastFired && (
                      <span className="text-xs text-surface-200">
                        Last fired: {new Date(alert.lastFired).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>

                {/* Toggle */}
                <button
                  onClick={() => toggleAlert(alert.id)}
                  className="ml-4 p-1"
                >
                  {alert.enabled ? (
                    <ToggleRight className="w-8 h-8 text-primary-600" />
                  ) : (
                    <ToggleLeft className="w-8 h-8 text-surface-200" />
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
