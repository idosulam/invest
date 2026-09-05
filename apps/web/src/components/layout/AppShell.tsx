"use client";

import { useAuth } from "@/lib/auth";
import { Sidebar } from "@/components/layout/Sidebar";
import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
  const { loading, token, user } = useAuth();

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-surface-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-6 h-6 animate-spin text-primary-500 mx-auto mb-3" />
          <p className="text-[13px] text-surface-500">Loading...</p>
        </div>
      </div>
    );
  }

  // Not authenticated — show children (login page) without shell
  if (!token || !user) {
    return <>{children}</>;
  }

  // Authenticated — show full app shell
  return (
    <div className="flex min-h-screen bg-surface-50">
      <Sidebar />
      <main className="flex-1 ml-56 p-6">{children}</main>
    </div>
  );
}
