"use client";

import { Bell } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";

export default function AlertsPage() {
  return (
    <div>
      <Header title="Alerts" subtitle="Configure alert rules and notification channels" />
      <Card>
        <div className="h-64 flex flex-col items-center justify-center text-surface-700">
          <Bell className="w-10 h-10 mb-2 text-surface-200" />
          <p className="font-medium">Alert Center</p>
          <p className="text-sm text-surface-200 mt-1">Coming in next batch</p>
        </div>
      </Card>
    </div>
  );
}
