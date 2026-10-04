"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, CalendarDays, Check, MapPin, Star } from "lucide-react";
import RaceMap, { RaceMapLocation } from "../components/ui/RaceMap";
import type { ScheduleEntry } from "../lib/circuits";

/* ═══════════════════════════════════════════════════════════════════════
   TRACKS EXPLORER

   The season's circuits as a map rather than a grid of cards. A grid says
   "here are 24 things"; the map says where they are and how the year moves
   between them, which is the part a list can't show.

   Selecting a marker opens a scrollable panel over the left of the map with
   that circuit's layout art. The map keeps rendering underneath and
   re-centres on the strip still visible beside the panel — same reason as
   the predictions dossier: resizing the map would re-project 177 country
   paths on every frame.
   ═══════════════════════════════════════════════════════════════════════ */

export type Track = {
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

/** Below this the panel would leave no usable map beside it. */
const SPLIT_MIN_WIDTH = 760;
const PANEL_WIDTH = 420;

const longDate = (iso: string) =>
    new Date(iso).toLocaleDateString("en-GB", {
        weekday: "short",
        day: "numeric",
        month: "long",
        year: "numeric",
    });

export default function TracksExplorer({
    tracks,
    season,
}: {
    tracks: Track[];
    season: number;
}) {
    const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
    const [splitLayout, setSplitLayout] = useState(false);
    const shellRef = useRef<HTMLDivElement>(null);

    /* The panel only sits *beside* the map when there's room for both; on a
       narrow screen it covers the map entirely and the inset drops to 0 so
       fly-to goes back to centring on the whole canvas. */
    useEffect(() => {
        const measure = () => {
            const width = shellRef.current?.offsetWidth ?? 0;
            setSplitLayout(width >= SPLIT_MIN_WIDTH);
        };
        measure();
        window.addEventListener("resize", measure);
        return () => window.removeEventListener("resize", measure);
    }, []);

    const onCalendar = tracks.filter((t) => t.onCalendar && t.round);
    const offCalendar = tracks.filter((t) => !t.onCalendar);

    /* The next round is the first one still ahead of us — the map paints it
       differently from the rest of the upcoming set. */
    const nextRound = onCalendar
        .filter((t) => !t.completed)
        .sort((a, b) => (a.round!.round ?? 0) - (b.round!.round ?? 0))[0]?.round?.round;

    const locations: RaceMapLocation[] = onCalendar.map((t) => ({
        slug: t.slug,
        name: t.name,
        locality: t.locality,
        lat: t.lat,
        long: t.long,
        round: t.round!.round,
        date: t.round!.date,
        status:
            t.round!.round === nextRound
                ? "next"
                : t.completed
                ? "completed"
                : "upcoming",
        note: t.completed ? "Raced this season" : undefined,
    }));

    const selected = tracks.find((t) => t.slug === selectedSlug) ?? null;
    const close = useCallback(() => setSelectedSlug(null), []);

    /* Escape closes the panel. Nothing else is layered here, so unlike the
       predictions overlay this is a single level of dismiss. */
    useEffect(() => {
        if (!selected) return;
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") close();
        };
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [selected, close]);

    return (
        <div className="flex flex-col gap-6">
            <div
                ref={shellRef}
                className="relative overflow-hidden rounded-[var(--radius-card)]
                           border border-line bg-ink-2
                           h-[clamp(420px,72vh,760px)]"
            >
                <RaceMap
                    locations={locations}
                    selectedSlug={selectedSlug}
                    onSelect={(location) => setSelectedSlug(location?.slug ?? null)}
                    zoomEnabled
                    zoomMin={0.8}
                    zoomMax={14}
                    initialZoom={1}
                    animationDuration={700}
                    focusInsetLeft={selected && splitLayout ? PANEL_WIDTH : 0}
                    showControls
                    showLegend
                    showTooltips
                />

                {/* Sync, not mode="wait": the panels are opaque and absolutely
                    positioned, so picking another circuit crossfades rather
                    than leaving a dead beat. */}
                <AnimatePresence>
                    {selected && (
                        <motion.aside
                            key={selected.slug}
                            initial={{ opacity: 0, x: -24 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -24 }}
                            transition={{ duration: 0.26, ease: [0.22, 0.61, 0.36, 1] }}
                            style={{ width: splitLayout ? PANEL_WIDTH : "100%" }}
                            className="absolute inset-y-0 left-0 z-30 flex flex-col
                                       border-r border-line-strong
                                       bg-ink-2/95 backdrop-blur-xl"
                        >
                            <CircuitPanel
                                track={selected}
                                season={season}
                                onClose={close}
                            />
                        </motion.aside>
                    )}
                </AnimatePresence>
            </div>

            {/* Circuits with artwork that aren't raced this year have nowhere
                to sit on a season map — kept here so the page still accounts
                for them rather than silently dropping them. */}
            {offCalendar.length > 0 && (
                <div>
                    <p className="label-xs mb-3">
                        Not on the {season} calendar
                    </p>
                    <div className="flex flex-wrap gap-3">
                        {offCalendar.map((track) => (
                            <div
                                key={track.slug}
                                className="card flex items-center gap-3 px-4 py-3"
                            >
                                {track.img && (
                                    <img
                                        src={track.img}
                                        alt=""
                                        aria-hidden
                                        loading="lazy"
                                        className="h-10 w-16 object-contain opacity-50"
                                    />
                                )}
                                <div className="min-w-0">
                                    <p className="h-card text-fg">{track.locality}</p>
                                    <p className="text-[11px] text-fg-subtle truncate">
                                        {track.name}
                                    </p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

/* ═══════════════════════════════════════════════════════════════════════
   ONE CIRCUIT
   ═══════════════════════════════════════════════════════════════════════ */

function CircuitPanel({
    track,
    season,
    onClose,
}: {
    track: Track;
    season: number;
    onClose: () => void;
}) {
    const round = track.round;

    return (
        <>
            <div className="shrink-0 px-5 pt-5 pb-4 border-b border-line">
                <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                        <p className="label-xs">
                            {round ? `Round ${round.round}` : `Not raced in ${season}`}
                        </p>
                        <h3 className="h-section text-fg mt-1 truncate">
                            {track.locality}
                        </h3>
                        <p className="text-[13px] text-fg-muted truncate">
                            {track.name}
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        aria-label="Back to the map"
                        className="shrink-0 grid place-items-center w-8 h-8
                                   rounded-[var(--radius-chip)] border border-line
                                   text-fg-muted hover:text-fg hover:bg-ink-4
                                   transition-colors"
                    >
                        <ArrowLeft className="w-4 h-4" />
                    </button>
                </div>

                <div className="flex flex-wrap items-center gap-2 mt-3">
                    {track.onCalendar && (
                        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full
                                         border border-warn/30 bg-warn/10 text-warn
                                         text-[10px] font-black uppercase tracking-[0.14em]">
                            <Star className="w-3 h-3 fill-current" />
                            {season} calendar
                        </span>
                    )}
                    {track.completed && (
                        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full
                                         border border-good/30 bg-good/10 text-good
                                         text-[10px] font-black uppercase tracking-[0.14em]">
                            <Check className="w-3 h-3" />
                            Raced
                        </span>
                    )}
                </div>
            </div>

            {/* Scrollable: the layout art is the thing worth looking at, so
                it gets the room and the panel scrolls rather than shrinking
                it to fit. */}
            <div className="flex-1 min-h-0 overflow-y-auto px-5 py-4 flex flex-col gap-4">
                {track.img ? (
                    <div className="rounded-[var(--radius-chip)] border border-line
                                    bg-ink-1 px-4 py-4">
                        <p className="label-xs mb-3">Circuit layout</p>
                        <img
                            src={track.img}
                            alt={`${track.name} layout`}
                            className="w-full max-h-[300px] object-contain
                                       drop-shadow-[0_0_30px_rgba(232,0,32,0.2)]"
                        />
                    </div>
                ) : (
                    <p className="text-[13px] text-fg-subtle">
                        No layout artwork available for this circuit yet.
                    </p>
                )}

                <div className="rounded-[var(--radius-chip)] border border-line bg-ink-1 p-4
                                flex flex-col gap-3">
                    {round && (
                        <div className="flex items-center gap-2.5">
                            <CalendarDays className="w-4 h-4 text-accent shrink-0" />
                            <div className="min-w-0">
                                <p className="label-xs">Race day</p>
                                <p className="text-[13px] font-semibold text-fg">
                                    {longDate(round.date)}
                                </p>
                            </div>
                        </div>
                    )}
                    <div className="flex items-center gap-2.5">
                        <MapPin className="w-4 h-4 text-accent shrink-0" />
                        <div className="min-w-0">
                            <p className="label-xs">Coordinates</p>
                            <p className="text-[13px] font-mono font-semibold text-fg num">
                                {track.lat.toFixed(3)}, {track.long.toFixed(3)}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}
