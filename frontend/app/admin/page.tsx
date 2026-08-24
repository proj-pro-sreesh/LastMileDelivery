"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { StatusBadge } from "@/components/StatusBadge";
import { useAuth } from "@/components/AuthProvider";
import { ApiError, get, patch, post } from "@/lib/api";
import { dateTime, money } from "@/lib/format";
import type { AgentInfo, Order, OrderStatus } from "@/lib/types";

const ALL_STATUSES: OrderStatus[] = [
  "PENDING",
  "ASSIGNED",
  "PICKED_UP",
  "IN_TRANSIT",
  "OUT_FOR_DELIVERY",
  "DELIVERED",
  "FAILED",
  "CANCELLED",
];

export default function AdminOrdersPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
    if (user && user.role !== "ADMIN") router.replace("/orders");
  }, [user, authLoading, router]);

  const refresh = useCallback(async () => {
    try {
      const query = statusFilter ? `?status=${statusFilter}` : "";
      const [list, agentList] = await Promise.all([get<Order[]>(`/orders${query}`), get<AgentInfo[]>("/admin/agents")]);
      setOrders(list);
      setAgents(agentList);
    } catch (err) {
      setMessage({ kind: "err", text: err instanceof ApiError ? err.message : "Load failed" });
    }
  }, [statusFilter]);

  useEffect(() => {
    if (user?.role === "ADMIN") refresh();
  }, [user, refresh]);

  async function act(label: string, fn: () => Promise<unknown>) {
    try {
      await fn();
      setMessage({ kind: "ok", text: label });
      await refresh();
    } catch (err) {
      setMessage({ kind: "err", text: err instanceof ApiError ? err.message : "Action failed" });
    }
  }

  const assignAgent = (o: Order, agentId: string) =>
    act(`Assigned to ${agents.find((a) => a.user_id === agentId)?.name ?? "agent"}`, () =>
      post(`/admin/orders/${o.id}/assign`, { agent_id: agentId }),
    );
  const autoAssign = (o: Order) =>
    act("Auto-assign complete", () => post(`/admin/orders/${o.id}/auto-assign`));
  const reschedule = (o: Order) =>
    act("Rescheduled for redelivery", () => post(`/admin/orders/${o.id}/reschedule`, {}));
  const override = (o: Order, status: OrderStatus) => {
     
    const remarks = window.prompt(`Remarks for overriding to ${status}:`)!;
    if (!remarks || remarks.length < 3) return;
    return act(`Order → ${status}`, () => patch(`/admin/orders/${o.id}/status`, { status, remarks }));
  };

  if (authLoading || !user || orders === null) return <p className="text-sm text-slate-400">Loading…</p>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">All orders</h1>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">All statuses</option>
          {ALL_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {message && (
        <p
          className={`rounded-lg px-3 py-2 text-sm ${
            message.kind === "ok" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
          }`}
        >
          {message.text}
        </p>
      )}

      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-slate-100 text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Order</th>
              <th className="px-4 py-3">Route</th>
              <th className="px-4 py-3">Total</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Agent</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {orders.map((o) => {
              const agent = agents.find((a) => a.user_id === o.assigned_agent_id);
              return (
                <tr key={o.id} className="align-top transition hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link href={`/orders/${o.id}`} className="font-mono text-xs font-medium text-blue-600 hover:underline">
                      {o.id.slice(0, 8)}
                    </Link>
                    <p className="mt-0.5 text-xs text-slate-400">{dateTime(o.created_at)}</p>
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {o.pickup_pincode} → {o.drop_pincode}
                    <span className="ml-1.5 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
                      {o.order_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-medium">{money(o.total_charge)}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={o.status} />
                    <p className="mt-1 text-xs text-slate-400">attempt #{o.delivery_attempt}</p>
                  </td>
                  <td className="px-4 py-3">
                    {agent ? (
                      <>
                        <p className="font-medium text-slate-800">{agent.name}</p>
                        <p className="text-xs text-slate-400">{agent.availability_status}</p>
                      </>
                    ) : (
                      <span className="text-xs italic text-slate-400">unassigned</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-1.5">
                      {o.status === "PENDING" && (
                        <div className="flex gap-1.5">
                          <button
                            onClick={() => autoAssign(o)}
                            className="rounded-md bg-blue-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-blue-700"
                          >
                            Auto-assign
                          </button>
                          <select
                            defaultValue=""
                            onChange={(e) => e.target.value && assignAgent(o, e.target.value)}
                            className="rounded-md border border-slate-300 px-2 py-1 text-xs"
                          >
                            <option value="">Assign…</option>
                            {agents
                              .filter((a) => a.availability_status === "AVAILABLE")
                              .map((a) => (
                                <option key={a.user_id} value={a.user_id}>
                                  {a.name} ({a.active_orders} active)
                                </option>
                              ))}
                          </select>
                        </div>
                      )}
                      {o.status === "FAILED" && (
                        <button
                          onClick={() => reschedule(o)}
                          className="rounded-md bg-amber-500 px-2.5 py-1 text-xs font-medium text-white hover:bg-amber-600"
                        >
                          Reschedule redelivery
                        </button>
                      )}
                      <select
                        defaultValue=""
                        onChange={(e) => e.target.value && override(o, e.target.value as OrderStatus)}
                        className="w-fit rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                      >
                        <option value="">Override status…</option>
                        {ALL_STATUSES.filter((s) => s !== o.status && !(o.status === "FAILED" && s === "PENDING")).map(
                          (s) => (
                            <option key={s} value={s}>
                              Force → {s}
                            </option>
                          ),
                        )}
                      </select>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
