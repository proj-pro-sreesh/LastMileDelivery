"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";
import { ApiError, get } from "@/lib/api";
import type { AgentInfo } from "@/lib/types";

const DOT: Record<string, string> = {
  AVAILABLE: "bg-emerald-500",
  BUSY: "bg-amber-500",
  OFFLINE: "bg-slate-400",
};

export default function AdminAgentsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
    if (user && user.role !== "ADMIN") router.replace("/orders");
  }, [user, authLoading, router]);

  useEffect(() => {
    if (user?.role !== "ADMIN") return;
    get<AgentInfo[]>("/admin/agents")
      .then(setAgents)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Load failed"));
  }, [user]);

  if (authLoading || !user) return <p className="text-sm text-slate-400">Loading…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900">Delivery agents</h1>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {agents.map((a) => (
          <article key={a.user_id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${DOT[a.availability_status]}`} />
              <h2 className="font-semibold text-slate-900">{a.name}</h2>
              <span className="ml-auto rounded bg-slate-100 px-2 py-0.5 text-[10px] font-medium uppercase text-slate-500">
                {a.vehicle_type ?? "no vehicle"}
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500">{a.email}</p>
            <dl className="mt-4 space-y-1.5 text-sm">
              <div className="flex justify-between">
                <dt className="text-slate-500">Status</dt>
                <dd className="font-medium capitalize">{a.availability_status.toLowerCase()}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Active orders</dt>
                <dd className="font-medium">{a.active_orders}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Last location</dt>
                <dd className="font-mono text-xs">
                  {a.latitude ? `${Number(a.latitude).toFixed(3)}, ${Number(a.longitude).toFixed(3)}` : "—"}
                </dd>
              </div>
            </dl>
          </article>
        ))}
        {agents.length === 0 && !error && (
          <p className="text-sm text-slate-400">No agents yet — run scripts/seed.py on the backend.</p>
        )}
      </div>
    </div>
  );
}
