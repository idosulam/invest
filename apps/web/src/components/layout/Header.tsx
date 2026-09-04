"use client";

import { useState, type ReactNode } from "react";
import { useAuth } from "@/lib/auth";
import { LogOut, User, ChevronDown, Shield } from "lucide-react";

interface HeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function Header({ title, subtitle, actions }: HeaderProps) {
  const { user, logout, isAdmin, isAnalyst } = useAuth();
  const [showMenu, setShowMenu] = useState(false);

  const roleBadge = user?.role === "ADMIN"
    ? { label: "Admin", color: "bg-red-500/10 text-danger-500" }
    : user?.role === "ANALYST"
    ? { label: "Analyst", color: "bg-blue-500/10 text-primary-400" }
    : { label: "Viewer", color: "bg-surface-100 text-surface-500" };

  return (
    <div className="flex items-center justify-between mb-6">
      <div>
        <h1 className="text-2xl font-bold text-white">{title}</h1>
        {subtitle && <p className="text-sm text-surface-500 mt-0.5">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-3">
        {actions}

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-surface-100 transition-colors"
          >
            <div className="w-8 h-8 bg-primary-500/10 rounded-full flex items-center justify-center">
              <User className="w-4 h-4 text-primary-400" />
            </div>
            <div className="text-left hidden md:block">
              <p className="text-sm font-medium text-white">{user?.username}</p>
              <span className={`inline-flex items-center px-1.5 py-0 text-[10px] font-medium rounded-full ${roleBadge.color}`}>
                {roleBadge.label}
              </span>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-surface-400" />
          </button>

          {/* Dropdown */}
          {showMenu && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
              <div className="absolute right-0 top-full mt-1 w-56 bg-surface-800 rounded-lg shadow-lg border border-surface-200 py-1 z-50">
                <div className="px-3 py-2 border-b border-surface-200">
                  <p className="text-sm font-medium text-white">{user?.username}</p>
                  <p className="text-xs text-surface-500">{user?.email}</p>
                </div>

                <div className="px-3 py-2 border-b border-surface-200">
                  <div className="flex items-center gap-2 text-xs text-surface-500">
                    <Shield className="w-3.5 h-3.5" />
                    <span>Role: {user?.role}</span>
                  </div>
                </div>

                <button
                  onClick={() => { setShowMenu(false); logout(); }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-danger-500 hover:bg-surface-100 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  Sign Out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
