"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { clsx } from "clsx";
import {
  LayoutDashboard,
  LineChart,
  ListOrdered,
  ScanLine,
  Compass,
  FlaskConical,
  Briefcase,
  Settings,
  Bell,
  Activity,
  Server,
  LogOut,
  User,
  Target,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/instruments", label: "Instruments", icon: LineChart },
  { href: "/watchlists", label: "Watchlists", icon: ListOrdered },
  { href: "/signals", label: "Signals", icon: Activity },
  { href: "/strategies", label: "Strategies", icon: Target },
  { href: "/scanner", label: "Scanner", icon: ScanLine },
  { href: "/discover", label: "Discover", icon: Compass },
  { href: "/backtests", label: "Backtests", icon: FlaskConical },
  { href: "/portfolios", label: "Portfolios", icon: Briefcase },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/operations", label: "Operations", icon: Server },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout, isAdmin } = useAuth();

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-56 bg-surface-100 border-r border-surface-300 flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 h-14 border-b border-surface-300">
        <div className="w-7 h-7 bg-primary-600 rounded flex items-center justify-center">
          <span className="text-xs font-bold text-white">MP</span>
        </div>
        <span className="text-sm font-semibold text-surface-800 tracking-tight">Market Platform</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          if (item.href === "/operations" && !isAdmin) return null;

          const isActive =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] font-medium transition-colors",
                isActive
                  ? "bg-primary-600/15 text-primary-400"
                  : "text-surface-500 hover:bg-surface-200 hover:text-surface-700"
              )}
            >
              <item.icon className="w-4 h-4 flex-shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* User section */}
      <div className="px-3 py-3 border-t border-surface-300">
        <div className="flex items-center gap-2.5 px-3 py-2">
          <div className="w-7 h-7 bg-surface-200 rounded-full flex items-center justify-center">
            <User className="w-3.5 h-3.5 text-surface-500" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[13px] font-medium text-surface-700 truncate">{user?.username}</p>
            <p className="text-[11px] text-surface-400">{user?.role}</p>
          </div>
          <button
            onClick={logout}
            className="p-1.5 rounded text-surface-400 hover:text-surface-700 hover:bg-surface-200 transition-colors"
            title="Sign out"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Footer */}
      <div className="px-5 py-2.5 border-t border-surface-300">
        <p className="text-[11px] text-surface-400">Research & paper trading only</p>
      </div>
    </aside>
  );
}
