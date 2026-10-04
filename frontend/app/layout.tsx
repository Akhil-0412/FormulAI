import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Dock from "./components/Dock";
import AppShell from "./components/AppShell";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "FormulAI — 2026 Intelligence Center",
  description: "Race prediction and live analysis for the 2026 F1 season",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-ink-0 text-fg`}
        suppressHydrationWarning
      >
        {/* The app sits as a rounded frame inset from a black page plane.
            Navigation floats over it as a dock rather than occupying a
            column, so the full frame width belongs to content. */}
        <div className="h-screen p-0 sm:p-3 lg:p-4">
          <div
            className="h-full rounded-none sm:rounded-[var(--radius-frame)]
                       bg-ink-1 border border-line overflow-hidden"
          >
            <AppShell>{children}</AppShell>
          </div>
        </div>

        <Dock />
      </body>
    </html>
  );
}
