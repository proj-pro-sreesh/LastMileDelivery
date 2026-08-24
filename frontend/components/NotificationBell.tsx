"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { get, post } from "@/lib/api";
import type { Notification } from "@/lib/types";

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const ref = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    try {
      const all = await get<Notification[]>("/notifications");
      const unreadList = await get<Notification[]>("/notifications?unread=true");
      setItems(all.slice(0, 15));
      setUnread(unreadList.length);
    } catch {
      /* signed out or backend down — bell stays quiet */
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  async function markRead(id: string) {
    await post(`/notifications/${id}/read`);
    refresh();
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative rounded-lg px-2 py-1.5 text-slate-300 transition hover:bg-slate-700 hover:text-white"
        aria-label="Notifications"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.7 21a2 2 0 0 1-3.4 0" />
        </svg>
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
            {unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 max-h-96 w-96 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
            <span className="text-sm font-semibold text-slate-800">Notifications</span>
            <button
              className="text-xs font-medium text-blue-600 hover:underline"
              onClick={async () => {
                await post("/notifications/read-all");
                refresh();
              }}
            >
              Mark all read
            </button>
          </div>
          {items.length === 0 && <p className="px-4 py-6 text-center text-sm text-slate-400">Nothing yet.</p>}
          {items.map((n) => (
            <button
              key={n.id}
              onClick={() => markRead(n.id)}
              className={`block w-full border-b border-slate-50 px-4 py-3 text-left transition hover:bg-slate-50 ${
                n.read_at ? "opacity-60" : ""
              }`}
            >
              <p className={`text-sm ${n.read_at ? "text-slate-600" : "font-semibold text-slate-900"}`}>{n.title}</p>
              <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{n.message}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
