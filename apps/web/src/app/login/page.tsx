"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { LogIn, UserPlus, Eye, EyeOff, AlertTriangle } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login, register, token, loading: authLoading } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!authLoading && token) {
      router.push("/");
    }
  }, [authLoading, token, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "register") {
        await register(email, username, password);
      } else {
        await login(username, password);
      }
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-surface-50 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-surface-300 border-t-primary-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (token) return null;

  return (
    <div className="min-h-screen bg-surface-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-primary-600 rounded-lg flex items-center justify-center mx-auto mb-4">
            <span className="text-xl font-bold text-white">MP</span>
          </div>
          <h1 className="text-xl font-bold text-surface-800">Market Platform</h1>
          <p className="text-[13px] text-surface-500 mt-1">Stock & ETF research</p>
        </div>

        {/* Card */}
        <div className="bg-surface-100 rounded-lg border border-surface-300 p-6">
          {/* Tabs */}
          <div className="flex mb-5 bg-surface-200 rounded-md p-0.5">
            <button
              onClick={() => { setMode("login"); setError(""); }}
              className={`flex-1 py-1.5 text-[13px] font-medium rounded transition-colors ${
                mode === "login"
                  ? "bg-surface-100 text-surface-800 shadow-sm"
                  : "text-surface-400 hover:text-surface-600"
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => { setMode("register"); setError(""); }}
              className={`flex-1 py-1.5 text-[13px] font-medium rounded transition-colors ${
                mode === "register"
                  ? "bg-surface-100 text-surface-800 shadow-sm"
                  : "text-surface-400 hover:text-surface-600"
              }`}
            >
              Create Account
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2 p-3 mb-4 bg-danger-50 border border-danger-600/20 rounded-md">
              <AlertTriangle className="w-4 h-4 text-danger-400 flex-shrink-0 mt-0.5" />
              <p className="text-[13px] text-danger-400">{error}</p>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-3.5">
            {mode === "register" && (
              <div>
                <label className="block text-[13px] font-medium text-surface-600 mb-1">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full"
                  placeholder="you@example.com"
                />
              </div>
            )}

            <div>
              <label className="block text-[13px] font-medium text-surface-600 mb-1">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full"
                placeholder="your_username"
              />
            </div>

            <div>
              <label className="block text-[13px] font-medium text-surface-600 mb-1">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  className="w-full pr-10"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 text-[13px] font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors mt-5"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : mode === "login" ? (
                <LogIn className="w-4 h-4" />
              ) : (
                <UserPlus className="w-4 h-4" />
              )}
              {loading ? "Please wait..." : mode === "login" ? "Sign In" : "Create Account"}
            </button>
          </form>

          {/* Hint */}
          <div className="mt-4 p-3 bg-surface-200/50 rounded-md">
            <p className="text-[12px] text-surface-400 leading-relaxed">
              <span className="font-medium text-surface-500">First time?</span> Create an account to get started.
              Admin users can manage data sources and system settings.
            </p>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-[11px] text-surface-400 mt-6">
          Research & paper trading only. Not financial advice.
        </p>
      </div>
    </div>
  );
}
