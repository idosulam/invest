"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";

interface User {
  id: string;
  email: string;
  username: string;
  role: "ADMIN" | "ANALYST" | "VIEWER";
  is_active: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
  isAdmin: boolean;
  isAnalyst: boolean;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  loading: true,
  login: async () => {},
  register: async () => {},
  logout: () => {},
  isAdmin: false,
  isAnalyst: false,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Load token from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem("token");
    const storedUser = localStorage.getItem("user");

    if (stored) {
      setToken(stored);
      if (storedUser) {
        try {
          setUser(JSON.parse(storedUser));
        } catch {}
      }
      // Verify token is still valid
      fetch("/api/v1/auth/me", {
        headers: { Authorization: `Bearer ${stored}` },
      })
        .then((res) => {
          if (res.ok) return res.json();
          throw new Error("Invalid token");
        })
        .then((userData) => {
          setUser(userData);
          localStorage.setItem("user", JSON.stringify(userData));
        })
        .catch(() => {
          // Token invalid — clear it
          localStorage.removeItem("token");
          localStorage.removeItem("user");
          setToken(null);
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  // Redirect to login if not authenticated (except for /login page)
  useEffect(() => {
    if (!loading && !token && pathname !== "/login") {
      router.push("/login");
    }
  }, [loading, token, pathname, router]);

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || "Login failed");
    }

    const data = await res.json();
    localStorage.setItem("token", data.access_token);
    setToken(data.access_token);

    // Fetch user info
    const meRes = await fetch("/api/v1/auth/me", {
      headers: { Authorization: `Bearer ${data.access_token}` },
    });
    if (meRes.ok) {
      const userData = await meRes.json();
      setUser(userData);
      localStorage.setItem("user", JSON.stringify(userData));
    }
  }, []);

  const register = useCallback(async (email: string, username: string, password: string) => {
    const res = await fetch("/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, username, password }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || "Registration failed");
    }

    // Auto-login after registration
    await login(username, password);
  }, [login]);

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setToken(null);
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        register,
        logout,
        isAdmin: user?.role === "ADMIN",
        isAnalyst: user?.role === "ANALYST" || user?.role === "ADMIN",
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
