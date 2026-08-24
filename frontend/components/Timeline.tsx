import { dateTime } from "@/lib/format";
import type { TrackingEvent } from "@/lib/types";

const DOT: Record<string, string> = {
  DELIVERED: "bg-emerald-500",
  FAILED: "bg-red-500",
  CANCELLED: "bg-zinc-400",
};

export function Timeline({ events }: { events: TrackingEvent[] }) {
  if (events.length === 0) return <p className="text-sm text-slate-500">No tracking events yet.</p>;

  return (
    <ol className="relative ml-3 border-l border-slate-200">
      {[...events].reverse().map((event) => (
        <li key={event.id} className="mb-6 ml-6 last:mb-0">
          <span
            className={`absolute -left-[7px] mt-1.5 h-3.5 w-3.5 rounded-full border-2 border-white ${
              DOT[event.status] ?? "bg-blue-500"
            }`}
          />
          <div className="flex flex-wrap items-center gap-x-2">
            <span className="text-sm font-semibold text-slate-800">{event.status.replace(/_/g, " ")}</span>
            <span className="text-xs text-slate-400">{dateTime(event.created_at)}</span>
          </div>
          {event.remarks && <p className="mt-0.5 text-sm text-slate-600">{event.remarks}</p>}
          {event.actor_name && <p className="text-xs text-slate-400">by {event.actor_name}</p>}
        </li>
      ))}
    </ol>
  );
}
