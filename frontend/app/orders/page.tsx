"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { StatusBadge } from "@/components/StatusBadge";
import { homeForRole, useAuth } from "@/components/AuthProvider";
import { ApiError, get, post } from "@/lib/api";
import { dateTime, money } from "@/lib/format";
import type { Order, QuoteBreakdown } from "@/lib/types";

const EMPTY = {
  pickup_address: "",
  pickup_pincode: "600001",
  drop_address: "",
  drop_pincode: "560001",
  length_cm: "30",
  breadth_cm: "20",
  height_cm: "10",
  actual_weight_kg: "2",
  order_type: "B2C" as const,
  payment_type: "PREPAID" as const,
};

export default function OrdersPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<{
    pickup_address: string;
    pickup_pincode: string;
    drop_address: string;
    drop_pincode: string;
    length_cm: string;
    breadth_cm: string;
    height_cm: string;
    actual_weight_kg: string;
    order_type: "B2B" | "B2C";
    payment_type: "PREPAID" | "COD";
  }>({ ...EMPTY });
  const [quote, setQuote] = useState<QuoteBreakdown | null>(null);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
    if (user && user.role !== "CUSTOMER") router.replace(homeForRole(user.role));
  }, [user, loading, router]);

  const refresh = useCallback(async () => {
    try {
      setOrders(await get<Order[]>("/orders"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load orders");
    }
  }, []);

  useEffect(() => {
    if (user?.role === "CUSTOMER") refresh();
  }, [user, refresh]);

  useEffect(() => {
    if (!showForm) return;
    const fields = ["pickup_pincode", "drop_pincode", "length_cm", "breadth_cm", "height_cm", "actual_weight_kg"];
    if (fields.some((f) => !(form as Record<string, string>)[f])) return;
    const timer = setTimeout(async () => {
      try {
        setQuote(
          await post<QuoteBreakdown>("/orders/quote", {
            pickup_pincode: form.pickup_pincode,
            drop_pincode: form.drop_pincode,
            length_cm: form.length_cm,
            breadth_cm: form.breadth_cm,
            height_cm: form.height_cm,
            actual_weight_kg: form.actual_weight_kg,
            order_type: form.order_type,
            payment_type: form.payment_type,
          }),
        );
        setQuoteError(null);
      } catch (err) {
        setQuote(null);
        setQuoteError(err instanceof ApiError ? err.message : "Quote unavailable");
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [form, showForm]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await post<Order>("/orders", form);
      setForm({ ...EMPTY });
      setShowForm(false);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Order creation failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading || !user || orders === null) {
    return <p className="text-sm text-slate-400">{loading ? "Loading…" : error ?? "No orders yet."}</p>;
  }

  const input =
    "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">My orders</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
        >
          {showForm ? "Close" : "+ New order"}
        </button>
      </div>

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {showForm && (
        <form onSubmit={submit} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <label className="text-sm font-medium text-slate-700 sm:col-span-2 lg:col-span-2">
              Pickup address
              <input required value={form.pickup_address} onChange={(e) => setForm({ ...form, pickup_address: e.target.value })} className={`mt-1 ${input}`} />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Pickup pincode
              <input required pattern="\d{6}" value={form.pickup_pincode} onChange={(e) => setForm({ ...form, pickup_pincode: e.target.value })} className={`mt-1 ${input}`} />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Drop pincode
              <input required pattern="\d{6}" value={form.drop_pincode} onChange={(e) => setForm({ ...form, drop_pincode: e.target.value })} className={`mt-1 ${input}`} />
            </label>
            <label className="text-sm font-medium text-slate-700 sm:col-span-2 lg:col-span-2">
              Drop address
              <input required value={form.drop_address} onChange={(e) => setForm({ ...form, drop_address: e.target.value })} className={`mt-1 ${input}`} />
            </label>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            {(["length_cm", "breadth_cm", "height_cm", "actual_weight_kg"] as const).map((field) => (
              <label key={field} className="text-sm font-medium capitalize text-slate-700">
                {field.replace("_cm", "").replace("actual_", "")}
                {field.endsWith("_kg") ? " (kg)" : " (cm)"}
                <input required type="number" step="0.01" min="0" value={form[field]} onChange={(e) => setForm({ ...form, [field]: e.target.value })} className={`mt-1 ${input}`} />
              </label>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap items-end gap-6">
            <div>
              <span className="text-sm font-medium text-slate-700">Type</span>
              <div className="mt-1 flex rounded-lg border border-slate-300 p-0.5">
                {(["B2B", "B2C"] as const).map((t) => (
                  <button type="button" key={t} onClick={() => setForm({ ...form, order_type: t })}
                    className={`rounded-md px-4 py-1.5 text-sm ${form.order_type === t ? "bg-blue-600 font-medium text-white" : "text-slate-600"}`}>
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <span className="text-sm font-medium text-slate-700">Payment</span>
              <div className="mt-1 flex rounded-lg border border-slate-300 p-0.5">
                {(["PREPAID", "COD"] as const).map((t) => (
                  <button type="button" key={t} onClick={() => setForm({ ...form, payment_type: t })}
                    className={`rounded-md px-4 py-1.5 text-sm ${form.payment_type === t ? "bg-blue-600 font-medium text-white" : "text-slate-600"}`}>
                    {t}
                  </button>
                ))}
              </div>
            </div>

            <div className="ml-auto min-w-56 rounded-xl bg-blue-50 p-4 text-sm ring-1 ring-inset ring-blue-100">
              <p className="font-semibold text-blue-900">Live quote</p>
              {quoteError && <p className="mt-1 text-xs text-red-600">{quoteError}</p>}
              {!quote && !quoteError && <p className="mt-1 text-xs text-blue-700/60">Fill dimensions to preview…</p>}
              {quote && (
                <dl className="mt-1 space-y-0.5 text-xs text-blue-900/80">
                  <div className="flex justify-between"><dt>Chargeable</dt><dd>{Number(quote.chargeable_weight_kg)} kg</dd></div>
                  <div className="flex justify-between"><dt>Base</dt><dd>{money(quote.base_charge)}</dd></div>
                  <div className="flex justify-between"><dt>COD surcharge</dt><dd>{money(quote.cod_surcharge)}</dd></div>
                  <div className="flex justify-between border-t border-blue-200 pt-1 text-sm font-bold text-blue-900"><dt>Total</dt><dd>{money(quote.total_charge)}</dd></div>
                </dl>
              )}
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="mt-5 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:opacity-50"
          >
            {submitting ? "Booking…" : `Book order${quote ? ` for ${money(quote.total_charge)}` : ""}`}
          </button>
        </form>
      )}

      {orders.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center text-sm text-slate-400">
          No orders yet — create your first one above.
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-100 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Order</th>
                <th className="px-4 py-3">Route</th>
                <th className="px-4 py-3">Charge</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Attempt</th>
                <th className="px-4 py-3">Booked</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {orders.map((o) => (
                <tr key={o.id} className="transition hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link href={`/orders/${o.id}`} className="font-mono text-xs font-medium text-blue-600 hover:underline">
                      {o.id.slice(0, 8)}
                    </Link>
                    <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
                      {o.order_type}/{o.payment_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {o.pickup_pincode} → {o.drop_pincode}
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-800">{money(o.total_charge)}</td>
                  <td className="px-4 py-3"><StatusBadge status={o.status} /></td>
                  <td className="px-4 py-3 text-slate-600">#{o.delivery_attempt}</td>
                  <td className="px-4 py-3 text-slate-500">{dateTime(o.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
