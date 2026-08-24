"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";
import { ApiError } from "@/lib/api";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", phone: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function set(field: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [field]: e.target.value });
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await register(form.name.trim(), form.email.trim(), form.phone.trim(), form.password);
      router.replace("/orders");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  const input =
    "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100";

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-bold text-slate-900">Create account</h1>
        <p className="mt-1 text-sm text-slate-500">Customer accounts only — staff are provisioned by admins.</p>

        <label className="mt-6 block text-sm font-medium text-slate-700">Full name</label>
        <input required value={form.name} onChange={set("name")} className={input} placeholder="Ada Lovelace" />

        <label className="mt-4 block text-sm font-medium text-slate-700">Email</label>
        <input required type="email" value={form.email} onChange={set("email")} className={input} placeholder="you@example.com" />

        <label className="mt-4 block text-sm font-medium text-slate-700">Phone (optional)</label>
        <input value={form.phone} onChange={set("phone")} className={input} placeholder="+91 99999 99999" />

        <label className="mt-4 block text-sm font-medium text-slate-700">Password</label>
        <input
          required
          type="password"
          minLength={8}
          value={form.password}
          onChange={set("password")}
          className={input}
          placeholder="Min 8 chars, upper + lower + digit"
        />

        {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="mt-6 w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
        >
          {busy ? "Creating…" : "Create account"}
        </button>

        <p className="mt-4 text-center text-sm text-slate-500">
          Already registered?{" "}
          <Link href="/login" className="font-medium text-blue-600 hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
