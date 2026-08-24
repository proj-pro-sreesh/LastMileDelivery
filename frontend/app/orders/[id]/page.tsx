"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { StatusBadge } from "@/components/StatusBadge";
import { Timeline } from "@/components/Timeline";
import { useAuth } from "@/components/AuthProvider";
import { ApiError, get, post } from "@/lib/api";
import { dateTime, money } from "@/lib/format";
import type { Order, TrackingEvent } from "@/lib/types";

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [order, setOrder] = useState<Order | null>(null);
  const [events, setEvents] = useState<TrackingEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [rescheduleDate, setRescheduleDate] = useState("");
  const [rescheduleBusy, setRescheduleBusy] = useState(false);
  const [rescheduleError, setRescheduleError] = useState<string | null>(null);
  const [rescheduleDone, setRescheduleDone] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [o, t] = await Promise.all([get<Order>(`/orders/${id}`), get<TrackingEvent[]>(`/orders/${id}/tracking`)]);
      setOrder(o);
      setEvents(t);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load order");
    }
  }, [id]);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [user, authLoading, router]);
  useEffect(() => {
    if (user) refresh();
  }, [user, refresh]);

  if (authLoading) return <p className="text-sm text-slate-400">Loading…</p>;
  if (error)
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
        {error} —{" "}
        <button className="font-medium underline" onClick={() => router.back()}>
          go back
        </button>
      </div>
    );
  if (!order) return <p className="text-sm text-slate-400">Loading order…</p>;

  const failedEvent = [...events].reverse().find((e) => e.status === "FAILED");
  const canReschedule = order.status === "FAILED" && user?.role === "CUSTOMER";

  async function submitReschedule() {
    if (!rescheduleDate || rescheduleBusy) return;
    setRescheduleBusy(true);
    setRescheduleError(null);
    try {
      await post<Order>(`/orders/${id}/reschedule`, {
        scheduled_delivery_date: rescheduleDate,
        remarks: "Rescheduled by customer",
      });
      setRescheduleDone(true);
      setRescheduleDate("");
      await refresh();
    } catch (err) {
      setRescheduleError(err instanceof ApiError ? err.message : "Could not reschedule the delivery");
    } finally {
      setRescheduleBusy(false);
    }
  }

  const rows: Array<[string, React.ReactNode]> = [
    ["Pickup", `${order.pickup_address} (${order.pickup_pincode})`],
    ["Drop", `${order.drop_address} (${order.drop_pincode})`],
    ["Parcel", `${order.length_cm}×${order.breadth_cm}×${order.height_cm} cm · ${order.actual_weight_kg} kg actual`],
    ["Chargeable weight", `${Number(order.chargeable_weight_kg)} kg (volumetric ${Number(order.volumetric_weight_kg)} kg)`],
    [
      "Charges",
      <>
        base {money(order.base_charge)}
        {Number(order.cod_surcharge) > 0 && <> + COD {money(order.cod_surcharge)}</>}
      </>,
    ],
    ["Type", `${order.order_type} · ${order.payment_type}`],
    ["Scheduled", order.scheduled_delivery_date ?? "—"],
    ["Delivery attempts", `#${order.delivery_attempt}`],
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-lg font-bold text-slate-900">{order.id.slice(0, 8)}</h1>
        <StatusBadge status={order.status} />
        <span className="ml-auto text-xl font-bold text-slate-900">{money(order.total_charge)}</span>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">Details</h2>
          <dl className="space-y-3 text-sm">
            {rows.map(([label, value]) => (
              <div key={label} className="flex justify-between gap-6">
                <dt className="shrink-0 text-slate-500">{label}</dt>
                <dd className="text-right font-medium text-slate-800">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-5 text-xs text-slate-400">
            Booked {dateTime(order.created_at)}
            {order.agent_name ? ` · Agent: ${order.agent_name}` : ""}
          </p>

          {canReschedule && (
            <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
              <p className="text-sm font-semibold text-amber-900">Delivery attempt failed</p>
              {failedEvent?.remarks && <p className="mt-1 text-xs text-amber-800">Reason: {failedEvent.remarks}</p>}
              {rescheduleDone ? (
                <p className="mt-3 text-xs font-medium text-emerald-700">
                  Redelivery scheduled — the order is back in the assignment queue.
                </p>
              ) : (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <input
                    type="date"
                    value={rescheduleDate}
                    min={new Date().toISOString().slice(0, 10)}
                    onChange={(e) => setRescheduleDate(e.target.value)}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-800 focus:border-indigo-500 focus:outline-none"
                  />
                  <button
                    onClick={submitReschedule}
                    disabled={!rescheduleDate || rescheduleBusy}
                    className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {rescheduleBusy ? "Rescheduling…" : "Reschedule delivery"}
                  </button>
                </div>
              )}
              {rescheduleError && <p className="mt-2 text-xs font-medium text-red-600">{rescheduleError}</p>}
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">Tracking timeline</h2>
          <Timeline events={events} />
        </section>
      </div>
    </div>
  );
}
