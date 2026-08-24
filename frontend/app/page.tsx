"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { homeForRole, useAuth } from "@/components/AuthProvider";
import Link from "next/link";

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (user) router.replace(homeForRole(user.role));
  }, [user, router]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-slate-50 px-4 text-center">
      <h1 className="text-4xl font-bold tracking-tight text-slate-900">
        LastMile<span className="text-blue-600">Tracker</span>
      </h1>
      <p className="max-w-md text-slate-500">
        Quote, book and track parcels end to end — with agent assignment, live status timelines and delivery retries.
      </p>
      {!loading && !user && (
        <div className="flex gap-3">
          <Link
            href="/login"
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700"
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
          >
            Create account
          </Link>
        </div>
      )}
    </div>
  );
}
