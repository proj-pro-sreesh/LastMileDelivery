"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { homeForRole, useAuth } from "@/components/AuthProvider";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const { login, user } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) {
    router.replace(homeForRole(user.role));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const me = await login(email.trim(), password);
      router.replace(homeForRole(me.role));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-bold text-slate-900">Sign in</h1>
        <p className="mt-1 text-sm text-slate-500">Welcome back to LastMile Tracker.</p>

        <label className="mt-6 block text-sm font-medium text-slate-700">Email</label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          placeholder="you@example.com"
        />

        <label className="mt-4 block text-sm font-medium text-slate-700">Password</label>
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          placeholder="••••••••"
        />

        {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="mt-6 w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>

        <p className="mt-4 text-center text-sm text-slate-500">
          No account?{" "}
          <Link href="/register" className="font-medium text-blue-600 hover:underline">
            Create one
          </Link>
        </p>
        <div className="mt-6 rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-400">
          Demo accounts — admin@lastmile-demo.com / Admin@123 · agent.vijay@lastmile-demo.com / Agent@123
        </div>
      </form>
    </div>
  );
}
