"use client";

import { useState } from "react";
import {
  Settings,
  Database,
  Key,
  Bell,
  Shield,
  Server,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
} from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";

const SECTIONS = [
  { id: "general", label: "General", icon: Settings },
  { id: "data", label: "Data Sources", icon: Database },
  { id: "auth", label: "Authentication", icon: Shield },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "system", label: "System", icon: Server },
];

export default function SettingsPage() {
  const [activeSection, setActiveSection] = useState("general");

  return (
    <div>
      <Header title="Settings" subtitle="System configuration and preferences" />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar */}
        <Card padding="sm">
          <nav className="space-y-1">
            {SECTIONS.map((s) => (
              <button
                key={s.id}
                onClick={() => setActiveSection(s.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  activeSection === s.id
                    ? "bg-primary-50 text-primary-700"
                    : "text-surface-700 hover:bg-surface-50"
                }`}
              >
                <s.icon className="w-4 h-4" />
                {s.label}
              </button>
            ))}
          </nav>
        </Card>

        {/* Content */}
        <div className="lg:col-span-3 space-y-6">
          {activeSection === "general" && <GeneralSettings />}
          {activeSection === "data" && <DataSourcesSettings />}
          {activeSection === "auth" && <AuthSettings />}
          {activeSection === "notifications" && <NotificationSettings />}
          {activeSection === "system" && <SystemSettings />}
        </div>
      </div>
    </div>
  );
}

/* ── General ── */

function GeneralSettings() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>General Settings</CardTitle>
      </CardHeader>
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-surface-900 mb-1">Platform Name</label>
          <input
            type="text"
            defaultValue="Market Platform"
            className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-surface-900 mb-1">Default Currency</label>
          <select className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2">
            <option>USD</option>
            <option>EUR</option>
            <option>GBP</option>
            <option>JPY</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-surface-900 mb-1">Timezone</label>
          <select className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2">
            <option>America/New_York</option>
            <option>America/Chicago</option>
            <option>Europe/London</option>
            <option>Asia/Tokyo</option>
            <option>Asia/Shanghai</option>
          </select>
        </div>
        <button className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700">
          Save Changes
        </button>
      </div>
    </Card>
  );
}

/* ── Data Sources ── */

function DataSourcesSettings() {
  const sources = [
    { name: "Yahoo Finance", status: "ok", type: "Free / Dev", lastFetch: "2 min ago" },
    { name: "SEC EDGAR", status: "ok", type: "Public", lastFetch: "1 hour ago" },
    { name: "CSV/Parquet Upload", status: "ok", type: "Manual", lastFetch: "—" },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Data Sources</CardTitle>
      </CardHeader>
      <div className="space-y-3">
        {sources.map((src) => (
          <div key={src.name} className="flex items-center justify-between p-3 bg-surface-50 rounded-lg">
            <div className="flex items-center gap-3">
              {src.status === "ok" ? (
                <CheckCircle className="w-5 h-5 text-success-500" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-warning-500" />
              )}
              <div>
                <p className="font-medium text-surface-900">{src.name}</p>
                <p className="text-xs text-surface-700">{src.type}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm text-surface-700">Last fetch: {src.lastFetch}</p>
              <button className="text-xs text-primary-600 hover:text-primary-700 flex items-center gap-1 mt-0.5">
                <RefreshCw className="w-3 h-3" /> Refresh
              </button>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

/* ── Auth ── */

function AuthSettings() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Authentication</CardTitle>
      </CardHeader>
      <div className="space-y-4">
        <div className="p-3 bg-surface-50 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Shield className="w-4 h-4 text-surface-700" />
            <p className="font-medium text-surface-900">Password Policy</p>
          </div>
          <ul className="text-sm text-surface-700 space-y-1 ml-6">
            <li>• Argon2 hashing</li>
            <li>• JWT tokens with configurable expiry</li>
            <li>• Role-based access control (Admin, Analyst, Viewer)</li>
          </ul>
        </div>
        <div>
          <label className="block text-sm font-medium text-surface-900 mb-1">JWT Token Expiry (minutes)</label>
          <input
            type="number"
            defaultValue={60}
            className="w-48 text-sm border border-surface-200 rounded-lg px-3 py-2"
          />
        </div>
      </div>
    </Card>
  );
}

/* ── Notifications ── */

function NotificationSettings() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Notification Channels</CardTitle>
      </CardHeader>
      <div className="space-y-4">
        <div className="p-3 bg-surface-50 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Bell className="w-4 h-4 text-surface-700" />
            <p className="font-medium text-surface-900">In-App Notifications</p>
          </div>
          <p className="text-sm text-surface-700 ml-6">Enabled — shows in the alerts panel</p>
        </div>
        <div className="p-3 bg-surface-50 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Key className="w-4 h-4 text-surface-700" />
            <p className="font-medium text-surface-900">Webhook</p>
          </div>
          <input
            type="text"
            placeholder="https://your-webhook-url.com/alerts"
            className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2 mt-1"
          />
        </div>
      </div>
    </Card>
  );
}

/* ── System ── */

function SystemSettings() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>System Health</CardTitle>
      </CardHeader>
      <div className="space-y-3">
        {[
          { name: "API Server", status: "Running", ok: true },
          { name: "PostgreSQL + TimescaleDB", status: "Connected", ok: true },
          { name: "Redis Cache", status: "Connected", ok: true },
          { name: "MinIO Object Storage", status: "Connected", ok: true },
          { name: "Prefect Workers", status: "Running", ok: true },
          { name: "Local LLM", status: "Not configured", ok: false },
        ].map((svc) => (
          <div key={svc.name} className="flex items-center justify-between p-3 bg-surface-50 rounded-lg">
            <div className="flex items-center gap-3">
              {svc.ok ? (
                <CheckCircle className="w-5 h-5 text-success-500" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-warning-500" />
              )}
              <span className="font-medium text-surface-900">{svc.name}</span>
            </div>
            <span className={`text-sm ${svc.ok ? "text-success-500" : "text-warning-500"}`}>
              {svc.status}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
