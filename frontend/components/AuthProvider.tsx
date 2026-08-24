"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { get, post } from "@/lib/api";
import type { Role, User } from "@/lib/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (name: string, email: string, phone: string, password: string) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  // Start as "not loading" when there is no stored token — avoids a pointless
  // loading flash and a synchronous setState inside the bootstrap effect.
  const [loading, setLoading] = useState<boolean>(() =>
    Boolean(typeof window !== "undefined" && window.localStorage.getItem("lmt.token")),
  );

  useEffect(() => {
    const token = window.localStorage.getItem("lmt.token");
    if (!token) return;
    let cancelled = false;
    get<User>("/auth/me")
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => window.localStorage.removeItem("lmt.token"))
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const persist = useCallback(async (token: string): Promise<User> => {
    window.localStorage.setItem("lmt.token", token);
    const me = await get<User>("/auth/me");
    setUser(me);
    return me;
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await post<{ access_token: string }>("/auth/login", { email, password });
      return persist(data.access_token);
    },
    [persist],
  );

  const register = useCallback(
    async (name: string, email: string, phone: string, password: string) => {
      await post("/auth/register", { name, email, phone: phone || null, password });
      const data = await post<{ access_token: string }>("/auth/login", { email, password });
      return persist(data.access_token);
    },
    [persist],
  );

  const logout = useCallback(() => {
    window.localStorage.removeItem("lmt.token");
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

export function homeForRole(role: Role): string {
  if (role === "ADMIN") return "/admin";
  if (role === "AGENT") return "/agent";
  return "/orders";
}
