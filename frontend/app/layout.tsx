import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "F1 Podium Predictor",
  description: "Advanced intelligence dashboard for the 2026 F1 Season",
};

import Sidebar from "./components/Sidebar";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-f1-navy text-f1-text h-screen flex overflow-hidden`}
      >
        <Sidebar />
        <main className="flex-1 ml-64 p-8 relative h-screen overflow-y-auto overflow-x-hidden">
          {/* Global Ambient Glow */}
          <div className="absolute top-0 right-0 w-[800px] h-[800px] bg-f1-red/5 rounded-full blur-[120px] pointer-events-none -translate-y-1/2 translate-x-1/3" />
          <div className="absolute bottom-0 left-0 w-[600px] h-[600px] bg-f1-teal/5 rounded-full blur-[100px] pointer-events-none translate-y-1/3 -translate-x-1/3" />

          <div className="relative z-10">
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}
