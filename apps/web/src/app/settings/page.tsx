"use client";

import { Settings } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";

export default function SettingsPage() {
  return (
    <div>
      <Header title="Settings" subtitle="System configuration and preferences" />
      <Card>
        <div className="h-64 flex flex-col items-center justify-center text-surface-700">
          <Settings className="w-10 h-10 mb-2 text-surface-200" />
          <p className="font-medium">Settings</p>
          <p className="text-sm text-surface-200 mt-1">Coming in next batch</p>
        </div>
      </Card>
    </div>
  );
}
