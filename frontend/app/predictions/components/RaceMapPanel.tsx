"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Expand, Globe2, X } from "lucide-react";
import RaceMap, { RaceMapLocation } from "../../components/ui/RaceMap";
import RaceDossier, { RaceResult } from "./RaceDossier";
import { useScrollContainerRef } from "../../lib/scrollContainer";

/* ═══════════════════════════════════════════════════════════════════════
   RACE MAP PANEL

   A preview of the season map that lives inline in the Predictions page,
   and expands into a focused overlay on click.

   The expansion is a hand-rolled FLIP rather than a shared-element
   `layoutId`: the overlay is fixed at its final geometry and starts life
   transformed back onto the preview's exact rect, then animates that
   transform to identity. Doing it this way means the map inside is laid
   out once at its final size — animating width/height instead would
   re-project 177 country paths on every frame of the zoom.

   Two map instances are alive while expanded (the preview keeps its place
   underneath so the close animation has somewhere to land). They share one
   topology fetch — see the module cache in RaceMap.
   ═══════════════════════════════════════════════════════════════════════ */

type Rect = { top: number; left: number; width: number; height: number };

/**
 * The overlay's resting geometry: the largest rect with the preview's own
 * aspect ratio that fits the viewport with margin. Matching the aspect
 * keeps the FLIP scale uniform, so nothing stretches on the way out.
 */
function fitToViewport(origin: Rect): Rect {
    const padX = Math.max(20, Math.min(72, window.innerWidth * 0.05));
    const padY = Math.max(20, Math.min(64, window.innerHeight * 0.06));
    const maxWidth = window.innerWidth - padX * 2;
    const maxHeight = window.innerHeight - padY * 2;

    const aspect = origin.width / origin.height;
    let width = maxWidth;
    let height = width / aspect;
    if (height > maxHeight) {
        height = maxHeight;
        width = height * aspect;
    }

    // A landscape preview in a portrait viewport can't grow at all while
    // holding its aspect — on a phone the "expanded" map would come out
    // narrower than the tile that opened it. Take the whole box instead
    // and accept a non-uniform scale on the way out; unfolding into the
    // spare vertical space is the point of expanding there.
    if (width < origin.width * 1.25) {
        width = maxWidth;
        height = maxHeight;
    }

    return {
        width,
        height,
        left: (window.innerWidth - width) / 2,
        top: (window.innerHeight - height) / 2,
    };
}

const toRect = (dom: DOMRect): Rect => ({
    top: dom.top,
    left: dom.left,
    width: dom.width,
    height: dom.height,
});

export default function RaceMapPanel({
    locations,
    season,
    results = {},
}: {
    locations: RaceMapLocation[];
    season: number;
    /** Backtest result per location slug, for rounds the model has scored. */
    results?: Record<string, RaceResult>;
}) {
    const previewRef = useRef<HTMLButtonElement>(null);
    const closeRef = useRef<HTMLButtonElement>(null);
    const scrollContainerRef = useScrollContainerRef();
    const reduceMotion = useReducedMotion();

    const [expanded, setExpanded] = useState(false);
    const [origin, setOrigin] = useState<Rect | null>(null);
    const [target, setTarget] = useState<Rect | null>(null);
    const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
    const [mounted, setMounted] = useState(false);

    useEffect(() => setMounted(true), []);

    const nextRace = locations.find((l) => l.status === "next") ?? null;
    const selected = locations.find((l) => l.slug === selectedSlug) ?? null;

    /* Selecting a round the model has already scored opens its dossier;
       selecting one it hasn't just names the circuit. */
    const dossier = selected ? results[selected.slug] ?? null : null;

    /* Below this the panel is too narrow to sit a map beside a dossier, so
       the dossier takes the whole thing and the map keeps its own centre. */
    const splitLayout = !!target && target.width >= 760;
    const dossierWidth = target
        ? splitLayout
            ? Math.min(500, target.width * 0.44)
            : target.width
        : 0;

    const measure = useCallback(() => {
        const dom = previewRef.current?.getBoundingClientRect();
        if (!dom) return;
        const from = toRect(dom);
        setOrigin(from);
        setTarget(fitToViewport(from));
    }, []);

    const open = useCallback(() => {
        measure();
        setExpanded(true);
    }, [measure]);

    const close = useCallback(() => setExpanded(false), []);

    /* ── Escape closes; the close button takes focus on open so Escape
          reaches the document even before the pointer moves. ────────── */
    useEffect(() => {
        if (!expanded) return;
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key !== "Escape") return;
            e.stopPropagation();
            // Escape peels one layer at a time: the open dossier first, the
            // map itself only once the map is all that's left.
            if (dossier) setSelectedSlug(null);
            else close();
        };
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [expanded, close, dossier]);

    /* ── Freeze the page behind the overlay. The app scrolls inside
          <main>, not the window, so that is the element to lock — and
          locking it is also what keeps the recorded origin rect valid
          for the return animation. ──────────────────────────────────── */
    useEffect(() => {
        const container = scrollContainerRef?.current;
        if (!expanded || !container) return;
        const previous = container.style.overflowY;
        container.style.overflowY = "hidden";
        return () => {
            container.style.overflowY = previous;
        };
    }, [expanded, scrollContainerRef]);

    /* ── A resize changes both ends of the transition. ─────────────── */
    useEffect(() => {
        if (!expanded) return;
        window.addEventListener("resize", measure);
        return () => window.removeEventListener("resize", measure);
    }, [expanded, measure]);

    /* ── Focus follows the overlay, and comes back to the tile that
          opened it — but only once it has actually been opened, or the
          first render would yank focus on page load. ────────────────── */
    const hasOpened = useRef(false);
    useEffect(() => {
        if (expanded) {
            hasOpened.current = true;
            closeRef.current?.focus();
        } else if (hasOpened.current) {
            previewRef.current?.focus({ preventScroll: true });
        }
    }, [expanded]);

    /* The transform that puts the overlay exactly on top of the preview.
       X and Y scale separately so the two rects line up edge-for-edge even
       when their aspects differ; on a landscape viewport they're equal and
       this is a plain uniform zoom. */
    const collapsed =
        origin && target
            ? {
                  x: origin.left - target.left,
                  y: origin.top - target.top,
                  scaleX: origin.width / target.width,
                  scaleY: origin.height / target.height,
              }
            : { x: 0, y: 0, scaleX: 0.9, scaleY: 0.9 };

    /* AnimatePresence has to outlive `expanded` for the collapse to play,
       so the overlay is mounted whenever a target rect exists and the
       *contents* are what come and go. */
    const overlay = target ? (
        <AnimatePresence onExitComplete={() => setSelectedSlug(null)}>
            {expanded && (
                <div
                    key="race-map-overlay"
                    className="fixed inset-0 z-[60]"
                    role="dialog"
                    aria-modal="true"
                    aria-label={`${season} season map`}
                >
                    <motion.div
                        className="absolute inset-0 bg-ink-0/80 backdrop-blur-sm"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.28, ease: "easeOut" }}
                        onClick={close}
                    />

                    <motion.div
                        className="absolute overflow-hidden rounded-[var(--radius-card)]
                                   border border-line-strong bg-ink-2
                                   shadow-[0_40px_120px_rgba(0,0,0,0.75)]"
                        style={{
                            top: target.top,
                            left: target.left,
                            width: target.width,
                            height: target.height,
                            transformOrigin: "top left",
                        }}
                        initial={reduceMotion ? { opacity: 0 } : collapsed}
                        animate={
                            reduceMotion
                                ? { opacity: 1 }
                                : { x: 0, y: 0, scaleX: 1, scaleY: 1 }
                        }
                        exit={reduceMotion ? { opacity: 0 } : collapsed}
                        transition={
                            reduceMotion
                                ? { duration: 0.15 }
                                : {
                                      type: "spring",
                                      stiffness: 220,
                                      damping: 30,
                                      mass: 0.9,
                                  }
                        }
                    >
                        <RaceMap
                            locations={locations}
                            selectedSlug={selectedSlug}
                            onSelect={(location) =>
                                setSelectedSlug(location?.slug ?? null)
                            }
                            zoomEnabled
                            zoomMin={0.8}
                            zoomMax={14}
                            initialZoom={1}
                            animationDuration={700}
                            focusInsetLeft={
                                dossier && splitLayout ? dossierWidth : 0
                            }
                            showControls
                            showLegend
                            showTooltips
                        />

                        {/* Chrome fades in once the panel has grown, so the
                            expansion itself reads as the map opening up
                            rather than a dialog assembling itself. */}
                        <motion.div
                            className="absolute inset-x-0 top-0 z-20 flex items-start justify-between
                                       gap-4 p-3 pointer-events-none"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0, transition: { duration: 0.12 } }}
                            transition={{ duration: 0.25, delay: 0.22 }}
                        >
                            <div className="w-px" />
                            <button
                                ref={closeRef}
                                type="button"
                                onClick={close}
                                className="pointer-events-auto flex items-center gap-2 pl-3 pr-2 py-1.5
                                           rounded-[var(--radius-chip)] border border-line-strong
                                           bg-ink-1/90 backdrop-blur-md text-fg-muted
                                           hover:text-fg hover:bg-ink-3 transition-colors"
                            >
                                <span className="label-xs !text-inherit">Close</span>
                                <kbd className="text-[10px] font-mono font-bold px-1.5 py-0.5
                                                rounded border border-line bg-ink-3 text-fg-subtle">
                                    ESC
                                </kbd>
                                <X className="w-4 h-4" />
                            </button>
                        </motion.div>

                        {/* ── Selection ────────────────────────────────
                           A scored round opens its dossier over the left of
                           the map (the map keeps rendering underneath and
                           re-centres on what's still visible, rather than
                           being resized — resizing would reproject all 177
                           country paths). A round with no result yet just
                           names the circuit. */}
                        {/* Sync, not mode="wait": these panels are opaque and
                            absolutely positioned, so an outgoing one can slide
                            out under the incoming one. Waiting would leave a
                            dead beat every time the user picks another race. */}
                        <AnimatePresence>
                            {dossier && selected ? (
                                <motion.aside
                                    key={`dossier-${selected.slug}`}
                                    initial={{ opacity: 0, x: -24 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    exit={{ opacity: 0, x: -24 }}
                                    transition={{ duration: 0.26, ease: [0.22, 0.61, 0.36, 1] }}
                                    style={{ width: dossierWidth }}
                                    className="absolute inset-y-0 left-0 z-30
                                               border-r border-line-strong
                                               bg-ink-2/95 backdrop-blur-xl"
                                >
                                    <RaceDossier
                                        location={selected}
                                        result={dossier}
                                        onClose={() => setSelectedSlug(null)}
                                    />
                                </motion.aside>
                            ) : selected ? (
                                <motion.div
                                    key={`chip-${selected.slug}`}
                                    initial={{ opacity: 0, y: 8 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: 8 }}
                                    transition={{ duration: 0.2 }}
                                    className="absolute bottom-3 left-3 z-20 max-w-[280px]
                                               rounded-[var(--radius-chip)] border border-line-strong
                                               bg-ink-1/90 backdrop-blur-md px-3.5 py-2.5"
                                >
                                    <p className="label-xs">
                                        {selected.round != null
                                            ? `Round ${selected.round}`
                                            : "Circuit"}
                                    </p>
                                    <p className="h-card text-fg mt-1">
                                        {selected.locality}
                                    </p>
                                    <p className="text-[12px] text-fg-muted leading-snug">
                                        {selected.name}
                                    </p>
                                    <p className="text-[11px] text-fg-subtle mt-1">
                                        {selected.note ??
                                            "Not raced yet — no result to score."}
                                    </p>
                                </motion.div>
                            ) : null}
                        </AnimatePresence>
                    </motion.div>
                </div>
            )}
        </AnimatePresence>
    ) : null;

    return (
        <>
            {/* ── Inline preview ───────────────────────────────────── */}
            <button
                ref={previewRef}
                type="button"
                onClick={open}
                aria-label={`Expand the ${season} season map`}
                className="group relative block w-full aspect-[16/9] min-h-[200px]
                           overflow-hidden rounded-[var(--radius-card)]
                           border border-line bg-ink-2 text-left
                           transition-colors hover:border-line-strong"
            >
                {/* Non-interactive inside the preview: the whole card is one
                    click target, but the markers keep pulsing. */}
                <RaceMap
                    locations={locations}
                    zoomEnabled={false}
                    initialZoom={1}
                    showControls={false}
                    showLegend={false}
                    showTooltips={false}
                />

                <div className="absolute inset-0 pointer-events-none flex flex-col justify-between p-3.5">
                    <div className="flex items-start justify-between gap-3">
                        <span className="flex items-center gap-2 px-2.5 py-1.5
                                         rounded-[var(--radius-chip)] border border-line
                                         bg-ink-1/80 backdrop-blur-md">
                            <Globe2 className="w-3.5 h-3.5 text-accent" />
                            <span className="label-xs">{season} season map</span>
                        </span>

                        {nextRace && (
                            <span className="flex items-center gap-2 px-2.5 py-1.5
                                             rounded-[var(--radius-chip)] border border-line
                                             bg-ink-1/80 backdrop-blur-md">
                                <span className="live-dot" />
                                <span className="label-xs">
                                    Next · {nextRace.locality}
                                </span>
                            </span>
                        )}
                    </div>

                    <span className="self-end flex items-center gap-2 px-2.5 py-1.5
                                     rounded-[var(--radius-chip)] border border-line
                                     bg-ink-1/80 backdrop-blur-md
                                     text-fg-muted group-hover:text-fg
                                     group-hover:border-line-strong transition-colors">
                        <Expand className="w-3.5 h-3.5" />
                        <span className="label-xs !text-inherit">
                            Click to explore
                        </span>
                    </span>
                </div>
            </button>

            {mounted && overlay ? createPortal(overlay, document.body) : null}
        </>
    );
}
