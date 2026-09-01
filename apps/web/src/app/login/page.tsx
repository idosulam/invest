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

  // Redirect if already authenticated
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
        <div className="w-8 h-8 border-2 border-primary-200 border-t-primary-600 rounded-full animate-spin" />
      </div>
    );
  }

  if (token) return null; // Will redirect

  return (
    <div className="min-h-screen bg-surface-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-primary-600 rounded-xl flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl font-bold text-white">MP</span>
          </div>
          <h1 className="text-2xl font-bold text-surface-900">Market Platform</h1>
          <p className="text-sm text-surface-700 mt-1">Stock & ETF Research Platform</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-xl shadow-sm border border-surface-200 p-6">
          {/* Tabs */}
          <div className="flex mb-6 bg-surface-100 rounded-lg p-1">
            <button
              onClick={() => { setMode("login"); setError(""); }}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
                mode === "login"
                  ? "bg-white text-surface-900 shadow-sm"
                  : "text-surface-700 hover:text-surface-900"
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => { setMode("register"); setError(""); }}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
                mode === "register"
                  ? "bg-white text-surface-900 shadow-sm"
                  : "text-surface-700 hover:text-surface-900"
              }`}
            >
              Create Account
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2 p-3 mb-4 bg-red-50 border border-red-200 rounded-lg">
              <AlertTriangle className="w-4 h-4 text-danger-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-danger-600">{error}</p>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" && (
              <div>
                <label className="block text-sm font-medium text-surface-900 mb-1">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="you@example.com"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-surface-900 mb-1">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                placeholder="your_username"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-surface-900 mb-1">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2.5 pr-10 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-700 hover:text-surface-900"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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

          {/* Demo hint */}
          <div className="mt-4 p-3 bg-surface-50 rounded-lg">
            <p className="text-xs text-surface-700">
              <span className="font-medium">First time?</span> Create an account to get started.
              Admin users can manage data sources and system settings.
            </p>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-surface-200 mt-6">
          Research & paper trading only. Not financial advice.
        </p>
      </div>
    </div>
  );
}
