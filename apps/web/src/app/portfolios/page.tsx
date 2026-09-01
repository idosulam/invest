"use client";

import { Briefcase } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";

export default function PortfoliosPage() {
  return (
    <div>
      <Header title="Portfolios" subtitle="Paper trading portfolios and analytics" />
      <Card>
        <div className="h-64 flex flex-col items-center justify-center text-surface-700">
          <Briefcase className="w-10 h-10 mb-2 text-surface-200" />
          <p className="font-medium">Portfolio Manager</p>
          <p className="text-sm text-surface-200 mt-1">Coming in next batch</p>
        </div>
      </Card>
    </div>
  );
}
