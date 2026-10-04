"use client";

import { ReactNode } from "react";

/* ── Section heading ──────────────────────────────────────────
   No icon-in-a-circle before the title. Four decorative pins on
   four sections encode nothing; the type carries the hierarchy.
   ───────────────────────────────────────────────────────────── */

export function SectionHeading({
    title,
    meta,
    right,
}: {
    title: string;
    meta?: string;
    right?: ReactNode;
}) {
    return (
        <div className="flex items-end justify-between gap-4 mb-4">
            <div className="flex items-baseline gap-3 min-w-0">
                <h2 className="h-section text-fg truncate">{title}</h2>
                {meta && (
                    <span className="label-xs shrink-0 hidden sm:block">{meta}</span>
                )}
            </div>
            {right && <div className="shrink-0">{right}</div>}
        </div>
    );
}

/* ── Chip row ─────────────────────────────────────────────────
   Horizontal selector. Scrolls rather than wrapping — a 24-round
   season would otherwise reflow into three ragged lines.
   ───────────────────────────────────────────────────────────── */

export type ChipItem = {
    id: string | number;
    top: string;      // e.g. "04"
    bottom?: string;  // e.g. "Tue"
    disabled?: boolean;
};

export function ChipRow({
    items,
    activeId,
    onSelect,
    ariaLabel = "Select",
}: {
    items: ChipItem[];
    activeId: string | number;
    onSelect: (id: string | number) => void;
    ariaLabel?: string;
}) {
    return (
        <div
            role="tablist"
            aria-label={ariaLabel}
            className="flex gap-2 overflow-x-auto no-scrollbar pb-1"
        >
            {items.map((it) => {
                const active = it.id === activeId;
                return (
                    <button
                        key={it.id}
                        role="tab"
                        aria-selected={active}
                        disabled={it.disabled}
                        onClick={() => onSelect(it.id)}
                        data-active={active}
                        className="chip shrink-0 min-w-[62px] px-3 py-2.5 text-center
                                   disabled:opacity-35 disabled:cursor-not-allowed"
                    >
                        <span className="block text-[15px] font-bold num leading-none">
                            {it.top}
                        </span>
                        {it.bottom && (
                            <span className="block text-[10px] mt-1 leading-none opacity-80">
                                {it.bottom}
                            </span>
                        )}
                    </button>
                );
            })}
        </div>
    );
}

/* ── Badge ────────────────────────────────────────────────── */

export function Badge({
    children,
    tone = "neutral",
}: {
    children: ReactNode;
    tone?: "neutral" | "accent" | "good" | "warn" | "live";
}) {
    const tones: Record<string, string> = {
        neutral: "bg-ink-4 text-fg-muted",
        accent: "bg-accent text-white",
        good: "bg-good/15 text-good",
        warn: "bg-warn/15 text-warn",
        live: "bg-live/15 text-live",
    };
    return (
        <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1
                        text-[11px] font-semibold num ${tones[tone]}`}
        >
            {tone === "live" && <span className="live-dot" />}
            {children}
        </span>
    );
}

/* ── Stat tile ────────────────────────────────────────────── */

export function StatTile({
    label,
    value,
    sub,
    accent = false,
}: {
    label: string;
    value: string;
    sub?: string;
    accent?: boolean;
}) {
    return (
        <div
            className={`rounded-[var(--radius-card)] p-5 border ${accent
                ? "bg-accent border-accent-hot"
                : "card"
                }`}
        >
            <p
                className={`label-xs mb-2 ${accent ? "text-white/70" : ""}`}
                style={accent ? { color: "rgba(255,255,255,0.72)" } : undefined}
            >
                {label}
            </p>
            <p
                className={`text-[34px] font-bold leading-none tracking-[-0.03em] ${accent ? "text-white" : "text-fg"
                    }`}
            >
                {value}
            </p>
            {sub && (
                <p
                    className={`text-[12px] mt-2 ${accent ? "text-white/70" : "text-fg-muted"}`}
                >
                    {sub}
                </p>
            )}
        </div>
    );
}

/* ── Empty / loading ──────────────────────────────────────── */

export function Placeholder({ lines = 3 }: { lines?: number }) {
    return (
        <div className="space-y-2.5 animate-pulse" aria-hidden>
            {Array.from({ length: lines }).map((_, i) => (
                <div
                    key={i}
                    className="h-3 rounded bg-ink-3"
                    style={{ width: `${88 - i * 14}%` }}
                />
            ))}
        </div>
    );
}

export function EmptyState({ message }: { message: string }) {
    return (
        <div className="py-10 text-center">
            <p className="text-[13px] text-fg-subtle">{message}</p>
        </div>
    );
}
