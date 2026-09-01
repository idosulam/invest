"use client";

import { useState, useEffect } from "react";
import {
  Server,
  Database,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  BarChart3,
  Loader2,
  Play,
} from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";

/* ── Types ── */

interface SystemStatus {
  total_instruments: number;
  active_instruments: number;
  total_bars: number;
  latest_bar_date: string | null;
  recent_jobs: { name: string; status: string; started: string; completed: string | null; rows: any }[];
  open_issues: number;
  quality_score: number;
}

interface JobRun {
  id: string;
  job_name: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  retries: number;
  row_counts: Record<string, number> | null;
  exception_details: string | null;
}

interface DataIssue {
  id: string;
  instrument_id: string | null;
  issue_type: string;
  severity: string;
  description: string;
  resolved: boolean;
  created_at: string;
}

/* ── Page ── */

export default function OperationsPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [jobs, setJobs] = useState<JobRun[]>([]);
  const [issues, setIssues] = useState<DataIssue[]>([]);
  const [loading, setLoading] = useState(true);
  const [ingesting, setIngesting] = useState(false);
  const [ingestSymbols, setIngestSymbols] = useState("AAPL,MSFT,GOOGL,NVDA,TSLA");

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statusRes, jobsRes, issuesRes] = await Promise.all([
        fetch("/api/v1/admin/status", { headers }),
        fetch("/api/v1/admin/jobs?limit=20", { headers }),
        fetch("/api/v1/admin/issues?resolved=false", { headers }),
      ]);
      if (statusRes.ok) setStatus(await statusRes.json());
      if (jobsRes.ok) setJobs(await jobsRes.json());
      if (issuesRes.ok) setIssues(await issuesRes.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const triggerIngest = async () => {
    setIngesting(true);
    try {
      const symbols = ingestSymbols.split(",").map((s) => s.trim()).filter(Boolean);
      const res = await fetch("/api/v1/admin/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({ symbols, timeframe: "1D" }),
      });
      if (res.ok) {
        const data = await res.json();
        alert(`Ingestion complete: ${data.inserted} inserted, ${data.updated} updated, ${data.rejected} rejected`);
        fetchData();
      }
    } catch (e) { console.error(e); }
    finally { setIngesting(false); }
  };

  const statusColor = (s: string) => {
    if (s === "SUCCESS") return "text-success-500";
    if (s === "FAILED") return "text-danger-500";
    return "text-warning-500";
  };

  const StatusIcon = ({ s }: { s: string }) => {
    if (s === "SUCCESS") return <CheckCircle className="w-4 h-4 text-success-500" />;
    if (s === "FAILED") return <XCircle className="w-4 h-4 text-danger-500" />;
    return <AlertTriangle className="w-4 h-4 text-warning-500" />;
  };

  return (
    <div>
      <Header
        title="Operations"
        subtitle="System health, data pipeline, and monitoring"
        actions={
          <button
            onClick={fetchData}
            className="flex items-center gap-1.5 px-3 py-2 text-sm border border-surface-200 rounded-lg hover:bg-surface-50"
          >
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        }
      />

      {loading ? (
        <div className="h-64 flex items-center justify-center text-surface-700">
          <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading system status...
        </div>
      ) : (
        <>
          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
            <Card padding="sm">
              <p className="text-xs text-surface-700 mb-1">Instruments</p>
              <p className="text-2xl font-bold text-surface-900">{status?.active_instruments ?? 0}</p>
              <p className="text-xs text-surface-200">{status?.total_instruments ?? 0} total</p>
            </Card>
            <Card padding="sm">
              <p className="text-xs text-surface-700 mb-1">Bars</p>
              <p className="text-2xl font-bold text-surface-900">{(status?.total_bars ?? 0).toLocaleString()}</p>
            </Card>
            <Card padding="sm">
              <p className="text-xs text-surface-700 mb-1">Latest Data</p>
              <p className="text-sm font-mono text-surface-900">
                {status?.latest_bar_date ? new Date(status.latest_bar_date).toLocaleDateString() : "—"}
              </p>
            </Card>
            <Card padding="sm">
              <p className="text-xs text-surface-700 mb-1">Open Issues</p>
              <p className={`text-2xl font-bold ${(status?.open_issues ?? 0) > 0 ? "text-warning-500" : "text-success-500"}`}>
                {status?.open_issues ?? 0}
              </p>
            </Card>
            <Card padding="sm">
              <p className="text-xs text-surface-700 mb-1">Quality Score</p>
              <p className="text-2xl font-bold text-success-500">
                {((status?.quality_score ?? 0) * 100).toFixed(0)}%
              </p>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Data Ingestion */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Data Ingestion</CardTitle>
              </CardHeader>

              <div className="flex gap-3 mb-4">
                <input
                  type="text"
                  value={ingestSymbols}
                  onChange={(e) => setIngestSymbols(e.target.value)}
                  placeholder="AAPL,MSFT,GOOGL"
                  className="flex-1 text-sm border border-surface-200 rounded-lg px-3 py-2"
                />
                <button
                  onClick={triggerIngest}
                  disabled={ingesting}
                  className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
                >
                  {ingesting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                  {ingesting ? "Ingesting..." : "Ingest"}
                </button>
              </div>

              {/* Recent jobs */}
              <h4 className="text-sm font-medium text-surface-900 mb-2">Recent Jobs</h4>
              {jobs.length === 0 ? (
                <p className="text-sm text-surface-700">No jobs run yet</p>
              ) : (
                <div className="space-y-2">
                  {jobs.map((job) => (
                    <div key={job.id} className="flex items-center justify-between p-3 bg-surface-50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <StatusIcon s={job.status} />
                        <div>
                          <p className="text-sm font-medium text-surface-900">{job.job_name}</p>
                          <p className="text-xs text-surface-200">
                            {new Date(job.started_at).toLocaleString()}
                            {job.completed_at && ` → ${new Date(job.completed_at).toLocaleTimeString()}`}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className={`text-xs font-medium ${statusColor(job.status)}`}>{job.status}</span>
                        {job.row_counts && (
                          <p className="text-xs text-surface-200">
                            {job.row_counts.inserted ?? 0} ins · {job.row_counts.updated ?? 0} upd · {job.row_counts.rejected ?? 0} rej
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Data Issues */}
            <Card>
              <CardHeader>
                <CardTitle>Open Issues</CardTitle>
              </CardHeader>

              {issues.length === 0 ? (
                <div className="h-48 flex flex-col items-center justify-center text-surface-700">
                  <CheckCircle className="w-10 h-10 mb-2 text-success-500" />
                  <p className="font-medium">No open issues</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {issues.map((issue) => (
                    <div key={issue.id} className="p-3 bg-surface-50 rounded-lg">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`px-1.5 py-0.5 text-xs rounded-full ${
                          issue.severity === "CRITICAL" ? "bg-red-50 text-danger-600"
                            : issue.severity === "HIGH" ? "bg-amber-50 text-warning-600"
                            : "bg-surface-100 text-surface-700"
                        }`}>{issue.severity}</span>
                        <span className="text-xs text-surface-200">{issue.issue_type}</span>
                      </div>
                      <p className="text-sm text-surface-900">{issue.description}</p>
                      <p className="text-xs text-surface-200 mt-1">{new Date(issue.created_at).toLocaleString()}</p>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
