"use client";

import { createContext, useContext, useRef, RefObject } from "react";

/**
 * The app's real scroll container.
 *
 * The app shell (layout.tsx) scrolls inside `<main>` via its own
 * `overflow-y-auto` — the outer `<html>`/`<body>` never scroll, their
 * height stays pinned to the viewport. Any component using Framer Motion's
 * `useScroll()` without an explicit `container` tracks *window* scroll by
 * default, which never changes here — a scroll-linked animation built
 * against the default would silently never progress, no matter how much
 * the user actually scrolls. This context exposes a ref to the real
 * scrolling element so `useScroll({ container })` tracks the right thing.
 */
const ScrollContainerContext = createContext<RefObject<HTMLElement | null> | null>(null);

export function useScrollContainerRef() {
    return useContext(ScrollContainerContext);
}

export function ScrollContainerProvider({
    containerRef,
    children,
}: {
    containerRef: RefObject<HTMLElement | null>;
    children: React.ReactNode;
}) {
    return (
        <ScrollContainerContext.Provider value={containerRef}>
            {children}
        </ScrollContainerContext.Provider>
    );
}
