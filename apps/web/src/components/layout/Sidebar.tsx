"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import {
  LayoutDashboard,
  LineChart,
  ListOrdered,
  ScanLine,
  FlaskConical,
  Briefcase,
  Settings,
  Bell,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/instruments", label: "Instruments", icon: LineChart },
  { href: "/watchlists", label: "Watchlists", icon: ListOrdered },
  { href: "/scanner", label: "Scanner", icon: ScanLine },
  { href: "/backtests", label: "Backtests", icon: FlaskConical },
  { href: "/portfolios", label: "Portfolios", icon: Briefcase },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-56 bg-surface-900 text-white flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-5 border-b border-surface-700">
        <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center font-bold text-sm">
          MP
        </div>
        <span className="text-lg font-semibold tracking-tight">Market Platform</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary-600 text-white"
                  : "text-surface-200 hover:bg-surface-800 hover:text-white"
              )}
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-surface-700 text-xs text-surface-200">
        <p>Research & paper trading only.</p>
        <p className="text-surface-700 mt-1">v0.1.0</p>
      </div>
    </aside>
  );
}
