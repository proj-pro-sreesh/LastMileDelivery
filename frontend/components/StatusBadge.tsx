import type { OrderStatus } from "@/lib/types";
import { statusClass } from "@/lib/format";

export function StatusBadge({ status }: { status: OrderStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${statusClass(status)}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
