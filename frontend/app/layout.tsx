import type { Metadata } from "next";

import { AppShell } from "@/components/AppShell";
import { AuthProvider } from "@/components/AuthProvider";

import "./globals.css";

export const metadata: Metadata = {
  title: "LastMile Tracker",
  description: "Last-mile delivery tracking demo",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
