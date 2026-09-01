"use client";

import { useState, type ReactNode } from "react";
import { useAuth } from "@/lib/auth";
import { LogOut, User, ChevronDown, Shield, BarChart3 } from "lucide-react";

interface HeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function Header({ title, subtitle, actions }: HeaderProps) {
  const { user, logout, isAdmin, isAnalyst } = useAuth();
  const [showMenu, setShowMenu] = useState(false);

  const roleBadge = user?.role === "ADMIN"
    ? { label: "Admin", color: "bg-red-50 text-danger-600" }
    : user?.role === "ANALYST"
    ? { label: "Analyst", color: "bg-blue-50 text-primary-600" }
    : { label: "Viewer", color: "bg-surface-100 text-surface-700" };

  return (
    <div className="flex items-center justify-between mb-6">
      <div>
        <h1 className="text-2xl font-bold text-surface-900">{title}</h1>
        {subtitle && <p className="text-sm text-surface-700 mt-0.5">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-3">
        {actions}

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-surface-100 transition-colors"
          >
            <div className="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center">
              <User className="w-4 h-4 text-primary-600" />
            </div>
            <div className="text-left hidden md:block">
              <p className="text-sm font-medium text-surface-900">{user?.username}</p>
              <span className={`inline-flex items-center px-1.5 py-0 text-[10px] font-medium rounded-full ${roleBadge.color}`}>
                {roleBadge.label}
              </span>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-surface-200" />
          </button>

          {/* Dropdown */}
          {showMenu && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
              <div className="absolute right-0 top-full mt-1 w-56 bg-white rounded-lg shadow-lg border border-surface-200 py-1 z-50">
                {/* User info */}
                <div className="px-3 py-2 border-b border-surface-100">
                  <p className="text-sm font-medium text-surface-900">{user?.username}</p>
                  <p className="text-xs text-surface-700">{user?.email}</p>
                </div>

                {/* Role info */}
                <div className="px-3 py-2 border-b border-surface-100">
                  <div className="flex items-center gap-2 text-xs text-surface-700">
                    <Shield className="w-3.5 h-3.5" />
                    <span>Role: {user?.role}</span>
                  </div>
                  {isAdmin && (
                    <p className="text-[10px] text-surface-200 mt-1 ml-5">
                      Full access to admin, data, and system settings
                    </p>
                  )}
                  {isAnalyst && !isAdmin && (
                    <p className="text-[10px] text-surface-200 mt-1 ml-5">
                      Can run backtests, generate signals, and manage instruments
                    </p>
                  )}
                </div>

                {/* Actions */}
                <button
                  onClick={() => {
                    setShowMenu(false);
                    logout();
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-danger-600 hover:bg-red-50 transition-colors"
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
