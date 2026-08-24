import type { OrderStatus } from "./types";

export function money(value: string | number): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  return `₹${n.toFixed(2)}`;
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const STATUS_STYLES: Record<OrderStatus, string> = {
  PENDING: "bg-slate-100 text-slate-700 ring-slate-300",
  ASSIGNED: "bg-blue-50 text-blue-700 ring-blue-300",
  PICKED_UP: "bg-indigo-50 text-indigo-700 ring-indigo-300",
  IN_TRANSIT: "bg-violet-50 text-violet-700 ring-violet-300",
  OUT_FOR_DELIVERY: "bg-amber-50 text-amber-700 ring-amber-300",
  DELIVERED: "bg-emerald-50 text-emerald-700 ring-emerald-300",
  FAILED: "bg-red-50 text-red-700 ring-red-300",
  CANCELLED: "bg-zinc-100 text-zinc-500 ring-zinc-300",
};

export function statusClass(status: OrderStatus): string {
  return STATUS_STYLES[status] ?? "bg-slate-100 text-slate-700 ring-slate-300";
}
