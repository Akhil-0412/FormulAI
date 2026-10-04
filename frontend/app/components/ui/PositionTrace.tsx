"use client";

import { useMemo, useState } from "react";
import { resolveDriver } from "../../constants/drivers";

/**
 * Finishing position by round — the whole field, podium in focus.
 *
 * Twenty-two overlapping lines is unreadable if they all compete, so the
 * field is pushed back to a single dim grey and only the current top three
 * carry colour and weight. Hovering any line pulls it forward in its own
 * colour, names the driver, and swaps the watermark, which makes the greyed
 * mass browsable instead of decorative.
 *
 * Y is inverted (P1 at the top) because that's how a results table reads;
 * anything outside the points is clamped to a floor band so a single DNF
 * doesn't stretch the scale and flatten everything above it.
 */

export type DriverSeries = {
    driverId: string;
    positions: (number | null)[];
    points: number;
};

export type ProjectedPoint = { driverId: string; position: number };

type Props = {
    rounds: { round: number; label: string }[];
    series: DriverSeries[];
    projection?: ProjectedPoint[];
    height?: number;
    depth?: number;
};

const FIELD = "#3a3a42";

/**
 * Fixed accent for whichever focused driver collides on team colour.
 *
 * A lightened version of the same hue (the previous approach) still reads
 * as "basically the same line" at a glance — that was the actual bug in
 * the screenshot, not just the dash. A genuinely different hue is what
 * makes two team-mates distinguishable, so this is a real colour, not a
 * tint. Silver-violet: doesn't collide with any current team's primary
 * (teal, red, blue, orange, green, grey, gold), and reads clearly on
 * black at 2px.
 */
const TWIN_COLOR = "#b98cff";

export default function PositionTrace({
    rounds,
    series,
    projection,
    height = 320,
    depth = 20,
}: Props) {
    const [hovered, setHovered] = useState<string | null>(null);

    const ranked = useMemo(
        () => [...series].sort((a, b) => b.points - a.points),
        [series]
    );

    /**
     * Focused drivers get a colour AND a dash pattern.
     *
     * Team-mates share a team colour, so two Mercedes lines in the top 3
     * would otherwise be the literal same stroke. Whichever one is ranked
     * lower gets bumped to TWIN_COLOR — a real, different hue, not a tint
     * of the team colour — plus a dash. The dash is a secondary encoding
     * on top of that, so the pair stays separable in greyscale and for
     * colour-vision deficiency, not only by hue. This is keyed off an
     * actual colour collision, not a hardcoded "P3 always gets the accent"
     * rule, so it still does the right thing if two team-mates land in
     * P1/P2 instead.
     */
    const focus = useMemo(() => {
        const map = new Map<string, { color: string; dash?: string }>();
        const usedHues = new Set<string>();

        ranked.slice(0, 3).forEach((s) => {
            const d = resolveDriver(s.driverId);
            const base = d?.color ?? "#e80020";
            const collides = usedHues.has(base);
            usedHues.add(base);
            map.set(s.driverId, {
                color: collides ? TWIN_COLOR : base,
                dash: collides ? "7 5" : undefined,
            });
        });
        return map;
    }, [ranked]);

    const W = 1000;
    const padL = 30;
    const padR = projection?.length ? 74 : 14;
    const padT = 14;
    const padB = 30;
    const plotW = W - padL - padR;
    const plotH = height - padT - padB;

    const n = rounds.length;
    const x = (i: number) => (n <= 1 ? padL : padL + (i / (n - 1)) * plotW);
    const y = (pos: number) => {
        const p = Math.min(Math.max(pos, 1), depth + 1);
        return padT + ((p - 1) / depth) * plotH;
    };

    /**
     * Catmull-Rom → cubic Bézier, run per contiguous segment so a DNF
     * breaks the line instead of the curve bridging across the gap.
     * Tangents are damped (÷8 rather than ÷6) because position data is
     * spiky — a P1→P18 swing would otherwise overshoot past the axis.
     */
    const smoothPath = (positions: (number | null)[]) => {
        const segments: { x: number; y: number }[][] = [];
        let cur: { x: number; y: number }[] = [];
        positions.forEach((p, i) => {
            if (p == null) {
                if (cur.length) segments.push(cur);
                cur = [];
                return;
            }
            cur.push({ x: x(i), y: y(p) });
        });
        if (cur.length) segments.push(cur);

        return segments
            .map((pts) => {
                if (pts.length === 1) {
                    return `M ${pts[0].x} ${pts[0].y} L ${pts[0].x + 0.01} ${pts[0].y}`;
                }
                let d = `M ${pts[0].x.toFixed(1)} ${pts[0].y.toFixed(1)}`;
                for (let i = 0; i < pts.length - 1; i++) {
                    const p0 = pts[i - 1] ?? pts[i];
                    const p1 = pts[i];
                    const p2 = pts[i + 1];
                    const p3 = pts[i + 2] ?? p2;
                    const c1x = p1.x + (p2.x - p0.x) / 8;
                    const c1y = p1.y + (p2.y - p0.y) / 8;
                    const c2x = p2.x - (p3.x - p1.x) / 8;
                    const c2y = p2.y - (p3.y - p1.y) / 8;
                    d += ` C ${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
                }
                return d;
            })
            .join(" ");
    };

    const lastIdx = n - 1;
    const projX = padL + plotW + 46;

    // Dim first, focused next, hovered last — painter's order is the
    // z-index here.
    const ordered = useMemo(() => {
        const isFocus = (id: string) => focus.has(id);
        return [
            ...series.filter((s) => !isFocus(s.driverId) && s.driverId !== hovered),
            ...series.filter((s) => isFocus(s.driverId) && s.driverId !== hovered),
            ...series.filter((s) => s.driverId === hovered),
        ];
    }, [series, focus, hovered]);

    const hoveredDriver = hovered ? resolveDriver(hovered) : undefined;
    const hoveredSeries = hovered ? series.find((s) => s.driverId === hovered) : undefined;

    // The watermark follows the hover, falling back to the championship
    // leader — so it always names whichever line you're reading.
    const markDriver = hoveredDriver ?? (ranked[0] ? resolveDriver(ranked[0].driverId) : undefined);
    const markColor = hovered
        ? hoveredDriver?.color ?? FIELD
        : focus.get(ranked[0]?.driverId ?? "")?.color ?? FIELD;

    return (
        <div className="relative" onMouseLeave={() => setHovered(null)}>
            {markDriver && (
                <div
                    className="absolute inset-0 flex items-center justify-center pointer-events-none select-none"
                    aria-hidden
                >
                    <span
                        key={markDriver.id}
                        className="font-bold tracking-[-0.05em] leading-none whitespace-nowrap"
                        style={{
                            fontSize: `clamp(48px, ${plotH * 0.5}px, 122px)`,
                            color: markColor,
                            opacity: hovered ? 0.13 : 0.07,
                            textTransform: "uppercase",
                            transition: "color 220ms ease, opacity 220ms ease",
                        }}
                    >
                        {markDriver.name.split(" ").pop()}
                    </span>
                </div>
            )}

            <svg
                viewBox={`0 0 ${W} ${height}`}
                className="w-full relative"
                style={{ height }}
                preserveAspectRatio="none"
                role="img"
                aria-label="Finishing position by round for the full field, current top three highlighted"
            >
                <rect
                    x={padL} y={y(1)} width={plotW} height={y(3) - y(1)}
                    fill="var(--color-accent)" opacity={0.05}
                />

                {[1, 3, 5, 10, 15, 20].map((p) => (
                    <line
                        key={p}
                        x1={padL} x2={padL + plotW} y1={y(p)} y2={y(p)}
                        stroke="var(--color-line)" strokeWidth={1}
                        vectorEffect="non-scaling-stroke"
                    />
                ))}

                {ordered.map((s) => {
                    const f = focus.get(s.driverId);
                    const isHovered = s.driverId === hovered;
                    const dimmed = hovered != null && !isHovered;
                    const d = resolveDriver(s.driverId);

                    const stroke = isHovered
                        ? d?.color ?? "var(--color-accent)"
                        : f && !dimmed
                            ? f.color
                            : FIELD;
                    const width = isHovered ? 3.2 : f ? 2.4 : 1.4;
                    const opacity = isHovered ? 1 : dimmed ? 0.18 : f ? 1 : 0.5;

                    const path = smoothPath(s.positions);
                    if (!path) return null;

                    // Race-day markers, only for lines in focus — 22 × 11 dots
                    // would be a field of noise.
                    const showDots = isHovered || (!!f && !dimmed);

                    return (
                        <g key={s.driverId}>
                            <path
                                d={path}
                                fill="none"
                                stroke={stroke}
                                strokeWidth={width}
                                strokeDasharray={isHovered ? undefined : f?.dash}
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                opacity={opacity}
                                vectorEffect="non-scaling-stroke"
                                style={{
                                    transition:
                                        "opacity 260ms cubic-bezier(0.22,0.61,0.36,1)," +
                                        "stroke 260ms ease, stroke-width 260ms ease",
                                }}
                            />

                            {showDots &&
                                s.positions.map((p, i) =>
                                    p == null ? null : (
                                        <circle
                                            key={i}
                                            cx={x(i)}
                                            cy={y(p)}
                                            r={isHovered ? 4.5 : 3.2}
                                            fill={stroke}
                                            stroke="var(--color-ink-2)"
                                            strokeWidth={2}
                                            vectorEffect="non-scaling-stroke"
                                            style={{ transition: "r 220ms ease, fill 260ms ease" }}
                                        />
                                    )
                                )}

                            <path
                                d={path}
                                fill="none"
                                stroke="transparent"
                                strokeWidth={16}
                                vectorEffect="non-scaling-stroke"
                                style={{ cursor: "pointer" }}
                                // onMouseOver rather than onMouseEnter: the hit
                                // path is a leaf so they're equivalent here, and
                                // mouseover bubbles, which keeps the behaviour
                                // reachable from delegated/synthetic events.
                                onMouseOver={() => setHovered(s.driverId)}
                                onFocus={() => setHovered(s.driverId)}
                            />
                        </g>
                    );
                })}

                {projection?.map((p) => {
                    const s = series.find((x) => x.driverId === p.driverId);
                    const d = resolveDriver(p.driverId);
                    if (!s) return null;
                    const lastPos = [...s.positions].reverse().find((v) => v != null);
                    if (lastPos == null) return null;
                    if (!focus.has(p.driverId) && hovered !== p.driverId) return null;
                    // Same colour resolution as the historical line — a
                    // driver who needed TWIN_COLOR there needs it here too,
                    // determined by the actual team-colour collision, not by
                    // which numeral the model happens to project them into.
                    const col = focus.get(p.driverId)?.color ?? d?.color ?? "var(--color-accent)";
                    const faded = hovered != null && hovered !== p.driverId;
                    return (
                        <g
                            key={`proj-${p.driverId}`}
                            style={{ transition: "opacity 260ms ease" }}
                            opacity={faded ? 0.15 : 0.85}
                        >
                            <path
                                d={`M ${x(lastIdx)} ${y(lastPos)} L ${projX} ${y(p.position)}`}
                                fill="none"
                                stroke={col}
                                strokeWidth={2}
                                strokeDasharray="6 5"
                                strokeLinecap="round"
                                vectorEffect="non-scaling-stroke"
                            />
                            <circle
                                cx={projX} cy={y(p.position)} r={4}
                                fill={col}
                                stroke="var(--color-ink-2)" strokeWidth={2}
                                vectorEffect="non-scaling-stroke"
                            />
                        </g>
                    );
                })}
            </svg>

            <div
                className="absolute left-0 top-0 pointer-events-none"
                style={{ height: height - padB, paddingTop: padT }}
            >
                {[1, 3, 5, 10, 15, 20].map((p) => (
                    <span
                        key={p}
                        className="absolute text-[10px] text-fg-subtle num"
                        style={{ top: `${((p - 1) / depth) * plotH - 6}px` }}
                    >
                        P{p}
                    </span>
                ))}
            </div>

            <div
                className="flex justify-between mt-1"
                style={{ paddingLeft: 30, paddingRight: projection?.length ? 74 : 14 }}
            >
                {rounds.map((r) => (
                    <span key={r.round} className="text-[9px] text-fg-subtle num">
                        {r.label}
                    </span>
                ))}
            </div>

            <div className="mt-3 min-h-[44px]">
                {hoveredDriver && hoveredSeries ? (
                    <div className="card-raised inline-flex items-center gap-3 px-3 py-2">
                        <span
                            className="w-2.5 h-2.5 rounded-full shrink-0"
                            style={{ backgroundColor: hoveredDriver.color }}
                        />
                        <div className="leading-tight">
                            <p className="text-[13px] font-semibold text-fg">
                                {hoveredDriver.name}
                            </p>
                            <p className="text-[11px]" style={{ color: hoveredDriver.color }}>
                                {hoveredDriver.team} · {hoveredSeries.points} pts
                            </p>
                        </div>
                    </div>
                ) : (
                    <div className="flex items-center gap-4 flex-wrap pt-1">
                        {ranked.slice(0, 3).map((s, i) => {
                            const d = resolveDriver(s.driverId);
                            const f = focus.get(s.driverId);
                            return (
                                <span
                                    key={s.driverId}
                                    className="flex items-center gap-2 text-[11px] text-fg-muted"
                                >
                                    <svg width="18" height="4" aria-hidden>
                                        <line
                                            x1="0" y1="2" x2="18" y2="2"
                                            stroke={f?.color ?? FIELD}
                                            strokeWidth="2.5"
                                            strokeDasharray={f?.dash}
                                            strokeLinecap="round"
                                        />
                                    </svg>
                                    <span className="num text-fg-subtle">P{i + 1}</span>
                                    {d?.name ?? s.driverId}
                                </span>
                            );
                        })}
                        <span className="flex items-center gap-2 text-[11px] text-fg-subtle">
                            <span className="w-4 h-[1.5px] rounded-full" style={{ backgroundColor: FIELD }} />
                            rest of the field — hover to identify
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
}
