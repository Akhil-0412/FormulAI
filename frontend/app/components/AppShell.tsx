"use client";

import { useRef } from "react";
import { ScrollContainerProvider } from "../lib/scrollContainer";

/**
 * Owns the ref to the real scrolling element (`<main>`) and exposes it via
 * context — see lib/scrollContainer.tsx for why this exists. Split out of
 * layout.tsx because that file exports `metadata`, which requires staying
 * a Server Component; refs need a Client Component.
 */
export default function AppShell({ children }: { children: React.ReactNode }) {
    const mainRef = useRef<HTMLElement>(null);

    return (
        <ScrollContainerProvider containerRef={mainRef}>
            <main
                ref={mainRef}
                className="h-full overflow-y-auto overflow-x-hidden p-3 lg:p-5"
            >
                {children}
                {/* Clearance so the dock never covers the last row. */}
                <div className="h-20" aria-hidden />
            </main>
        </ScrollContainerProvider>
    );
}
