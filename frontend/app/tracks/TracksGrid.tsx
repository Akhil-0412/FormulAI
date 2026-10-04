"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Star, Check, X } from "lucide-react";
import type { ScheduleEntry } from "../lib/circuits";

type Track = {
    slug: string;
    name: string;
    locality: string;
    img: string;
    round?: ScheduleEntry;
    onCalendar: boolean;
    completed: boolean;
    lat: number;
    long: number;
};

const MONTH = (iso: string) =>
    new Date(iso).toLocaleDateString("en-GB", { month: "long", year: "numeric" });

/**
 * Status badge: gold star for "on this year's calendar", a ring around the
 * card for "already raced". The two are independent — a completed round
 * keeps its star (it's still part of this year) and gains the ring; an
 * upcoming round has the star alone; a library-only circuit (has art, isn't
 * being raced this year — e.g. Sakhir, dropped from 2026) has neither.
 */
function StatusTooltip({ track, season }: { track: Track; season: number }) {
    if (!track.onCalendar || !track.round) {
        return <span>Not on the {season} calendar</span>;
    }
    return (
        <span>
            Round {track.round.round} · {MONTH(track.round.date)}
            {track.completed ? " · completed" : " · upcoming"}
        </span>
    );
}

export default function TracksGrid({
    tracks,
    season,
}: {
    tracks: Track[];
    season: number;
}) {
    const [selected, setSelected] = useState<Track | null>(null);

    useEffect(() => {
        if (!selected) return;
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") setSelected(null);
        };
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [selected]);

    return (
        <>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
                {tracks.map((track) => (
                    <motion.button
                        key={track.slug}
                        type="button"
                        layoutId={`card-${track.slug}`}
                        onClick={() => setSelected(track)}
                        className={`card card-interactive relative p-4 flex flex-col items-center
                                    text-center min-h-[180px] cursor-pointer
                                    ${track.completed ? "ring-1 ring-accent/40" : ""}`}
                    >
                        {track.onCalendar && (
                            <span
                                className="absolute top-3 right-3 flex items-center gap-1"
                                title={track.completed ? "Raced" : "On the calendar"}
                            >
                                {track.completed && (
                                    <Check className="w-3.5 h-3.5 text-accent" />
                                )}
                                <Star className="w-3.5 h-3.5 text-warn fill-warn" />
                            </span>
                        )}

                        <h4 className="h-card text-fg">{track.locality}</h4>
                        <p className="text-[10px] text-fg-subtle line-clamp-1 mt-0.5">
                            {track.name}
                        </p>

                        <div className="mt-auto pt-3 w-full flex justify-center">
                            {track.img ? (
                                <motion.img
                                    layoutId={`img-${track.slug}`}
                                    src={track.img}
                                    alt={track.locality}
                                    className="h-16 object-contain opacity-75"
                                />
                            ) : (
                                <span className="text-xs text-fg-subtle opacity-50">—</span>
                            )}
                        </div>
                    </motion.button>
                ))}
            </div>

            {/* ── Circuit detail ───────────────────────────────────────
               The card grows into the detail view rather than swapping to
               it — the same layoutId sits on the card and on its artwork. */}
            <AnimatePresence>
                {selected && (
                    <div
                        key="track-detail"
                        className="fixed inset-0 z-[60] flex items-center justify-center p-4"
                        role="dialog"
                        aria-modal="true"
                        aria-label={selected.name}
                    >
                        <motion.div
                            className="absolute inset-0 bg-ink-0/85 backdrop-blur-sm"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.25 }}
                            onClick={() => setSelected(null)}
                        />

                        <motion.div
                            layoutId={`card-${selected.slug}`}
                            className="card card-raised relative z-10 w-full max-w-3xl
                                       p-6 lg:p-10 flex flex-col items-center"
                        >
                            <button
                                type="button"
                                onClick={() => setSelected(null)}
                                aria-label="Close"
                                className="absolute top-4 right-4 grid place-items-center w-9 h-9
                                           rounded-[var(--radius-chip)] border border-line
                                           text-fg-muted hover:text-fg hover:bg-ink-4
                                           transition-colors"
                            >
                                <X className="w-4 h-4" />
                            </button>

                            <motion.div
                                initial={{ opacity: 0, y: -12 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.12 }}
                                className="text-center mb-6"
                            >
                                <h2 className="h-display text-fg mb-1">
                                    {selected.locality}
                                </h2>
                                <p className="text-fg-muted text-[15px]">{selected.name}</p>
                                <p className="label-xs mt-2">
                                    <StatusTooltip track={selected} season={season} />
                                </p>
                            </motion.div>

                            <div className="relative w-full flex items-center justify-center min-h-[240px]">
                                {selected.img ? (
                                    <motion.img
                                        layoutId={`img-${selected.slug}`}
                                        src={selected.img}
                                        alt={selected.name}
                                        className="max-h-[46vh] w-full object-contain
                                                   drop-shadow-[0_0_30px_rgba(232,0,32,0.25)]"
                                    />
                                ) : (
                                    <p className="text-center text-fg-subtle text-sm">
                                        No layout artwork available for this circuit yet.
                                    </p>
                                )}
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
        </>
    );
}
