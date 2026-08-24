"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { NotificationBell } from "@/components/NotificationBell";
import { homeForRole, useAuth } from "@/components/AuthProvider";

const LINKS = [
  { role: "CUSTOMER", href: "/orders", label: "My Orders" },
  { role: "AGENT", href: "/agent", label: "My Assignments" },
  { role: "ADMIN", href: "/admin", label: "Orders" },
  { role: "ADMIN", href: "/admin/agents", label: "Agents" },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-400">Loading…</div>
    );
  }
  if (!user || pathname === "/login" || pathname === "/register") return <>{children}</>;

  const links = LINKS.filter((l) => l.role === user.role);

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-40 bg-slate-900">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
          <Link href={homeForRole(user.role)} className="text-sm font-bold tracking-tight text-white">
            LastMile<span className="text-blue-400">Tracker</span>
          </Link>
          <nav className="flex gap-1">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={`rounded-lg px-3 py-1.5 text-sm transition ${
                  pathname.startsWith(l.href)
                    ? "bg-slate-700 font-medium text-white"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                {l.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <NotificationBell />
            <span className="hidden text-sm text-slate-300 sm:block">{user.name}</span>
            <button
              onClick={() => {
                logout();
                router.push("/login");
              }}
              className="rounded-lg px-3 py-1.5 text-sm text-slate-300 transition hover:bg-slate-700 hover:text-white"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
