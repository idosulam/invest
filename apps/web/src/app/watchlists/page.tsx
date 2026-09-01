"use client";

import { ListOrdered } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Header } from "@/components/layout/Header";

export default function WatchlistsPage() {
  return (
    <div>
      <Header title="Watchlists" subtitle="Track instruments you care about" />
      <Card>
        <div className="h-64 flex flex-col items-center justify-center text-surface-700">
          <ListOrdered className="w-10 h-10 mb-2 text-surface-200" />
          <p className="font-medium">Watchlists</p>
          <p className="text-sm text-surface-200 mt-1">Coming in next batch</p>
        </div>
      </Card>
    </div>
  );
}
