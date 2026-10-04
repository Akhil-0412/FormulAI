"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform, MotionValue } from "framer-motion";
import { useScrollContainerRef } from "../../lib/scrollContainer";

/**
 * Scroll-pinned narrative: "how the prediction engine works", ending at the
 * Run Prediction button.
 *
 * Mechanism: a tall container (500vh — one screen-height per chapter) holds
 * a `sticky top-0 h-screen` viewport. `useScroll` tracks scroll progress
 * through that tall container as a 0–1 value; each chapter is assigned a
 * band of that range and cross-fades in/out as progress enters/leaves its
 * band, via `useTransform`. The page never jump-cuts between chapters —
 * scrolling *is* the transition, which is the whole point of the pinned
 * pattern (as opposed to chapters that just sit in normal document flow).
 *
 * Each chapter has a placeholder visual built from the same motif described
 * in its Veo prompt (particle convergence, node clusters, branching tree,
 * parallel trails, rising beams), so swapping in a generated clip later is
 * a drop-in — replace the marked <div data-video-slot> content with a
 * <video> tag; the layout and crossfade timing don't change.
 *
 * Every per-chapter `useTransform` call lives inside its own small
 * component (ProgressDot / ChapterText / ChapterVisualLayer) rather than
 * inside the CHAPTERS.map() callback in the parent. Calling a hook inside a
 * .map() in the parent's own render body breaks the rules of hooks — even
 * though CHAPTERS has a fixed length here and it would work in practice,
 * it's still flagged by the lint rule and is fragile if the array ever
 * became dynamic. Each child component instance calls the hook once, at
 * its own top level, which is the compliant version of the same idea.
 */

const CHAPTERS = [
    {
        eyebrow: "01 — Ingestion",
        title: "Every race becomes data",
        body: "Qualifying times, finishing positions, pit stops, weather — pulled from Jolpica's public F1 archive, race by race, back to 2014. 263 races. 5,347 driver-results, paginated properly this time.",
    },
    {
        eyebrow: "02 — Feature engineering",
        title: "Raw results become signal",
        body: "Grid position, recent form, circuit history, Elo head-to-head ratings, constructor reliability, championship pressure — roughly 70 engineered features per driver, per race.",
    },
    {
        eyebrow: "03 — Learning to rank",
        title: "The model learns to rank, not guess",
        body: "An ensemble of XGBoost LambdaMART and LightGBM, trained specifically on 2022 onward — the ground-effect regulation era. Older seasons run a different formula; mixing them in hurt more than it helped.",
    },
    {
        eyebrow: "04 — Simulation",
        title: "Every outcome, simulated 10,000 times",
        body: "The model's ranking becomes a probability distribution across the full grid. Monte Carlo draws 10,000 simulated races from it, and a Plackett-Luce softmax calibrates the podium call.",
    },
] as const;

const BAND = 1 / CHAPTERS.length;

function ChapterVisual({ index, local }: { index: number; local: MotionValue<number> }) {
    if (index === 0) {
        // Converging particle trails toward centre.
        return (
            <svg viewBox="0 0 400 400" className="w-full h-full">
                {Array.from({ length: 16 }).map((_, i) => {
                    const angle = (i / 16) * Math.PI * 2;
                    const x1 = 200 + Math.cos(angle) * 180;
                    const y1 = 200 + Math.sin(angle) * 180;
                    return (
                        <motion.line
                            key={i}
                            x1={x1} y1={y1} x2={200} y2={200}
                            stroke={i % 3 === 0 ? "var(--color-accent)" : "var(--color-line-strong)"}
                            strokeWidth={1.5}
                            style={{ pathLength: local, opacity: local }}
                        />
                    );
                })}
                <circle cx={200} cy={200} r={4} fill="var(--color-accent)" />
            </svg>
        );
    }

    if (index === 1) {
        // Node clusters.
        const clusters = [
            [110, 130], [280, 110], [200, 220], [120, 290], [290, 280],
        ];
        return (
            <svg viewBox="0 0 400 400" className="w-full h-full">
                {clusters.map(([cx, cy], i) => (
                    <g key={i}>
                        {clusters.map(([ox, oy], j) =>
                            j > i ? (
                                <motion.line
                                    key={j}
                                    x1={cx} y1={cy} x2={ox} y2={oy}
                                    stroke="var(--color-line-strong)"
                                    strokeWidth={1}
                                    style={{ opacity: local }}
                                />
                            ) : null
                        )}
                    </g>
                ))}
                {clusters.map(([cx, cy], i) => (
                    <motion.circle
                        key={i}
                        cx={cx} cy={cy} r={10}
                        fill="var(--color-accent)"
                        style={{ scale: local, opacity: local }}
                    />
                ))}
            </svg>
        );
    }

    if (index === 2) {
        // Branching tree.
        return (
            <svg viewBox="0 0 400 400" className="w-full h-full">
                <motion.line x1={200} y1={40} x2={200} y2={120} stroke="var(--color-accent)" strokeWidth={2} style={{ pathLength: local }} />
                {[-1, 1].map((s) => (
                    <g key={s}>
                        <motion.line x1={200} y1={120} x2={200 + s * 80} y2={200} stroke="var(--color-line-strong)" strokeWidth={1.5} style={{ pathLength: local }} />
                        <motion.line x1={200 + s * 80} y1={200} x2={200 + s * 60} y2={290} stroke="var(--color-line-strong)" strokeWidth={1.5} style={{ pathLength: local }} />
                        <motion.line x1={200 + s * 80} y1={200} x2={200 + s * 140} y2={280} stroke="var(--color-line-strong)" strokeWidth={1.5} style={{ pathLength: local }} />
                    </g>
                ))}
            </svg>
        );
    }

    // index 3 — Parallel converging trails (Monte Carlo).
    return (
        <svg viewBox="0 0 400 400" className="w-full h-full">
            {Array.from({ length: 24 }).map((_, i) => {
                const startX = 20 + (i / 24) * 360;
                return (
                    <motion.path
                        key={i}
                        d={`M ${startX} 40 Q ${200 + (startX - 200) * 0.3} 220 200 360`}
                        fill="none"
                        stroke={i % 5 === 0 ? "var(--color-accent)" : "var(--color-line-strong)"}
                        strokeWidth={1}
                        style={{ pathLength: local, opacity: 0.5 }}
                    />
                );
            })}
        </svg>
    );
}

function ProgressDot({ index, scrollYProgress }: { index: number; scrollYProgress: MotionValue<number> }) {
    const opacity = useTransform(
        scrollYProgress,
        [index * BAND - BAND * 0.3, index * BAND, (index + 1) * BAND, (index + 1) * BAND + BAND * 0.3],
        [0.25, 1, 1, 0.25]
    );
    return <motion.span className="w-1.5 h-1.5 rounded-full bg-accent" style={{ opacity }} />;
}

function ChapterText({
    chapter,
    index,
    scrollYProgress,
}: {
    chapter: (typeof CHAPTERS)[number];
    index: number;
    scrollYProgress: MotionValue<number>;
}) {
    const opacity = useTransform(
        scrollYProgress,
        [index * BAND, index * BAND + BAND * 0.2, (index + 1) * BAND - BAND * 0.2, (index + 1) * BAND],
        [0, 1, 1, 0]
    );
    const y = useTransform(scrollYProgress, [index * BAND, index * BAND + BAND * 0.2], [24, 0]);

    return (
        <motion.div style={{ opacity, y }} className="absolute inset-0 flex flex-col justify-center">
            <p className="label-xs mb-3 text-accent">{chapter.eyebrow}</p>
            <h2 className="h-display text-fg mb-4 text-balance">{chapter.title}</h2>
            <p className="text-[15px] text-fg-muted leading-relaxed max-w-md">{chapter.body}</p>
        </motion.div>
    );
}

function ChapterVisualLayer({ index, scrollYProgress }: { index: number; scrollYProgress: MotionValue<number> }) {
    const opacity = useTransform(
        scrollYProgress,
        [index * BAND, index * BAND + BAND * 0.2, (index + 1) * BAND - BAND * 0.2, (index + 1) * BAND],
        [0, 1, 1, 0]
    );
    // Local progress within just this chapter's own band, for the visual's
    // internal draw-on animation — independent of the crossfade opacity.
    const local = useTransform(scrollYProgress, [index * BAND, (index + 1) * BAND], [0, 1]);

    return (
        <motion.div style={{ opacity }} className="absolute inset-0 p-10">
            <ChapterVisual index={index} local={local} />
        </motion.div>
    );
}

export default function ScrollStory() {
    const containerRef = useRef<HTMLDivElement>(null);
    // The app scrolls inside <main>, not the window — see
    // lib/scrollContainer.tsx. Without passing `container` here,
    // scrollYProgress tracks window scroll, which never moves, and every
    // chapter would sit frozen on chapter one regardless of how much the
    // user actually scrolls.
    const scrollContainerRef = useScrollContainerRef();
    const { scrollYProgress } = useScroll({
        target: containerRef,
        container: scrollContainerRef ?? undefined,
        offset: ["start start", "end end"],
    });

    const introOpacity = useTransform(scrollYProgress, [0, BAND * 0.5], [1, 0]);

    return (
        <div ref={containerRef} style={{ height: `${CHAPTERS.length * 100}vh` }} className="relative">
            <div className="sticky top-0 h-screen flex items-center overflow-hidden">
                {/* Progress rail */}
                <div className="absolute left-4 md:left-8 top-1/2 -translate-y-1/2 flex flex-col gap-3 z-20">
                    {CHAPTERS.map((_, i) => (
                        <ProgressDot key={i} index={i} scrollYProgress={scrollYProgress} />
                    ))}
                </div>

                <div className="max-w-[1500px] w-full mx-auto px-6 md:px-16 grid grid-cols-1 md:grid-cols-2 gap-10 items-center">
                    {/* Text column — each chapter cross-fades in its band */}
                    <div className="relative h-[280px]">
                        {CHAPTERS.map((ch, i) => (
                            <ChapterText key={ch.title} chapter={ch} index={i} scrollYProgress={scrollYProgress} />
                        ))}
                    </div>

                    {/* Visual column */}
                    <div className="relative h-[280px] md:h-[400px]">
                        <div
                            data-video-slot
                            className="absolute inset-0 rounded-[var(--radius-card)] border border-dashed border-line-strong
                                       bg-ink-2 overflow-hidden flex items-center justify-center"
                        >
                            {/* Swap this block for a <video autoPlay muted loop playsInline
                                src="/assets/story/chapter-N.mp4" className="w-full h-full object-cover" />
                                once you have generated clips — layout and crossfade stay the same. */}
                            {CHAPTERS.map((_, i) => (
                                <ChapterVisualLayer key={i} index={i} scrollYProgress={scrollYProgress} />
                            ))}
                            <span className="absolute bottom-3 right-3 label-xs opacity-50">
                                video slot · {CHAPTERS.length} chapters
                            </span>
                        </div>
                    </div>
                </div>

                {/* Scroll cue, only visible on the first chapter */}
                <motion.div
                    style={{ opacity: introOpacity }}
                    className="absolute bottom-8 left-1/2 -translate-x-1/2 label-xs flex flex-col items-center gap-2"
                >
                    <span>Scroll to see how it works</span>
                    <motion.span
                        animate={{ y: [0, 6, 0] }}
                        transition={{ repeat: Infinity, duration: 1.6 }}
                        className="w-4 h-4 border-b-2 border-r-2 border-fg-subtle rotate-45"
                        aria-hidden
                    />
                </motion.div>
            </div>
        </div>
    );
}
