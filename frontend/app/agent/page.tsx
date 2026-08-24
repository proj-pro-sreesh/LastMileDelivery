"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { StatusBadge } from "@/components/StatusBadge";
import { useAuth } from "@/components/AuthProvider";
import { ApiError, get, patch } from "@/lib/api";
import { money } from "@/lib/format";
import type { Order, OrderStatus } from "@/lib/types";

const NEXT_STEP: Partial<Record<OrderStatus, OrderStatus>> = {
  ASSIGNED: "PICKED_UP",
  PICKED_UP: "IN_TRANSIT",
  IN_TRANSIT: "OUT_FOR_DELIVERY",
  OUT_FOR_DELIVERY: "DELIVERED",
};

const STEP_LABEL: Record<string, string> = {
  PICKED_UP: "Pick up parcel",
  IN_TRANSIT: "Start transit",
  OUT_FOR_DELIVERY: "Out for delivery",
};

export default function AgentPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [availability, setAvailability] = useState("AVAILABLE");
  const [coords, setCoords] = useState({ latitude: "", longitude: "", pincode: "" });
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
    if (user && user.role !== "AGENT") router.replace("/orders");
  }, [user, authLoading, router]);

  const refresh = useCallback(async () => {
    try {
      const list = await get<Order[]>("/agent/orders");
      setOrders(list);
    } catch {
      setOrders([]);
    }
  }, []);

  useEffect(() => {
    if (user?.role === "AGENT") refresh();
  }, [user, refresh]);

  async function advance(order: Order, target: OrderStatus, remarks?: string) {
    try {
      await patch(`/agent/orders/${order.id}/status`, { status: target, remarks });
      setMessage({ kind: "ok", text: `Order ${order.id.slice(0, 8)} → ${target}` });
      await refresh();
    } catch (err) {
      setMessage({ kind: "err", text: err instanceof ApiError ? err.message : "Update failed" });
    }
  }

  async function fail(order: Order) {
     
    const reason = window.prompt(`Failure reason for ${order.id.slice(0, 8)}:`);
    if (!reason?.trim()) return;
    await advance(order, "FAILED", reason.trim());
  }

  async function saveAvailability(status: string) {
    setAvailability(status);
    try {
      await patch("/agent/availability", { availability_status: status });
      setMessage({ kind: "ok", text: `You are now ${status}` });
    } catch (err) {
      setMessage({ kind: "err", text: err instanceof ApiError ? err.message : "Could not update availability" });
    }
  }

  async function saveLocation(e: React.FormEvent) {
    e.preventDefault();
    try {
      const payload: Record<string, unknown> = {};
      if (coords.latitude) payload.latitude = coords.latitude;
      if (coords.longitude) payload.longitude = coords.longitude;
      if (coords.pincode) payload.pincode = coords.pincode;
      await patch("/agent/location", payload);
      setMessage({ kind: "ok", text: "Location updated — you'll be matched by nearest-distance" });
    } catch (err) {
      setMessage({ kind: "err", text: err instanceof ApiError ? err.message : "Could not update location" });
    }
  }

  if (authLoading || !user || orders === null) return <p className="text-sm text-slate-400">Loading…</p>;

  const active = orders.filter((o) => !["PENDING", "DELIVERED", "CANCELLED"].includes(o.status));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">My assignments</h1>
        <label className="flex items-center gap-2 text-sm">
          <span className="font-medium text-slate-700">Availability</span>
          <select
            value={availability}
            onChange={(e) => saveAvailability(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          >
            <option value="AVAILABLE">Available</option>
            <option value="OFFLINE">Offline</option>
          </select>
        </label>
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

      <form onSubmit={saveLocation} className="flex flex-wrap items-end gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <span className="w-full text-sm font-semibold text-slate-700">Update my location</span>
        {(
          [
            ["latitude", "Latitude"],
            ["longitude", "Longitude"],
            ["pincode", "Zone pincode"],
          ] as const
        ).map(([field, label]) => (
          <input
            key={field}
            value={coords[field]}
            onChange={(e) => setCoords({ ...coords, [field]: e.target.value })}
            placeholder={label}
            className="w-40 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        ))}
        <button type="submit" className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-900">
          Save location
        </button>
      </form>

      {active.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center text-sm text-slate-400">
          No active assignments right now.
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {active.map((o) => {
            const next = NEXT_STEP[o.status];
            return (
              <article key={o.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-center gap-3">
                  <Link href={`/orders/${o.id}`} className="font-mono text-sm font-bold text-blue-600 hover:underline">
                    {o.id.slice(0, 8)}
                  </Link>
                  <StatusBadge status={o.status} />
                  <span className="ml-auto text-sm font-semibold">{money(o.total_charge)}</span>
                </div>
                <p className="mt-2 text-sm text-slate-600">
                  {o.pickup_pincode} → {o.drop_pincode} · attempt #{o.delivery_attempt}
                </p>

                <div className="mt-4 flex flex-wrap gap-2">
                  {next && next !== "FAILED" && (
                    <button
                      onClick={() => advance(o, next)}
                      className={`rounded-lg px-3.5 py-2 text-sm font-medium text-white transition ${
                        o.status === "OUT_FOR_DELIVERY" ? "bg-emerald-600 hover:bg-emerald-700" : "bg-blue-600 hover:bg-blue-700"
                      }`}
                    >
                      {STEP_LABEL[next] ?? next}
                    </button>
                  )}
                  {o.status === "OUT_FOR_DELIVERY" && (
                    <button onClick={() => fail(o)} className="rounded-lg bg-red-600 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-red-700">
                      Mark failed…
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Completed</h2>
        {orders.filter((o) => ["DELIVERED", "FAILED", "CANCELLED"].includes(o.status)).length === 0 ? (
          <p className="text-sm text-slate-400">Nothing completed yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white shadow-sm">
            {orders
              .filter((o) => ["DELIVERED", "FAILED", "CANCELLED"].includes(o.status))
              .map((o) => (
                <li key={o.id} className="flex items-center gap-3 px-5 py-3 text-sm">
                  <Link href={`/orders/${o.id}`} className="font-mono text-xs text-blue-600 hover:underline">
                    {o.id.slice(0, 8)}
                  </Link>
                  <StatusBadge status={o.status} />
                  <span className="ml-auto text-slate-400">attempt #{o.delivery_attempt}</span>
                </li>
              ))}
          </ul>
        )}
      </section>
    </div>
  );
}
