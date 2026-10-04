"use client";

import { useMemo, useState } from "react";

/**
 * Model accuracy against the qualifying baseline, by round.
 *
 * Hand-rolled SVG rather than a chart library: this is one chart with
 * one shape, and pulling in a charting dependency to draw two paths
 * costs more than it saves.
 *
 * The dashed line is the qualifying-order baseline — the thing the
 * model has to beat to be worth running. Keeping it permanently on
 * screen is the point, not decoration.
 */

export type AccuracyPoint = {
    round: number;
    label: string;      // "R04" / "Suzuka"
    model: number | null;    // correct podium slots, 0..3
    baseline: number | null; // same metric for grid order
};

type Props = {
    data: AccuracyPoint[];
    height?: number;
};

const MAX = 3;

export default function AccuracyChart({ data, height = 210 }: Props) {
    const [hover, setHover] = useState<number | null>(null);

    const W = 1000;
    const H = height;
    const padL = 26;
    const padR = 8;
    const padT = 12;
    const padB = 26;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;

    const pts = data.length;

    const x = (i: number) =>
        pts <= 1 ? padL + plotW / 2 : padL + (i / (pts - 1)) * plotW;
    const y = (v: number) => padT + plotH - (v / MAX) * plotH;

    /** Catmull-Rom → cubic Bézier, so the line curves like the reference
     *  without overshooting into impossible values. */
    const smooth = (vals: (number | null)[]) => {
        const p = vals
            .map((v, i) => (v == null ? null : { x: x(i), y: y(v) }))
            .filter(Boolean) as { x: number; y: number }[];
        if (p.length === 0) return "";
        if (p.length === 1) return `M ${p[0].x} ${p[0].y}`;

        let d = `M ${p[0].x} ${p[0].y}`;
        for (let i = 0; i < p.length - 1; i++) {
            const p0 = p[i - 1] ?? p[i];
            const p1 = p[i];
            const p2 = p[i + 1];
            const p3 = p[i + 2] ?? p2;
            const c1x = p1.x + (p2.x - p0.x) / 6;
            const c1y = p1.y + (p2.y - p0.y) / 6;
            const c2x = p2.x - (p3.x - p1.x) / 6;
            const c2y = p2.y - (p3.y - p1.y) / 6;
            d += ` C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2.x} ${p2.y}`;
        }
        return d;
    };

    const modelPath = useMemo(() => smooth(data.map((d) => d.model)), [data, H]);
    const basePath = useMemo(() => smooth(data.map((d) => d.baseline)), [data, H]);

    const areaPath = useMemo(() => {
        if (!modelPath) return "";
        const last = data.map((d) => d.model).reduce<number>(
            (acc, v, i) => (v == null ? acc : i), -1);
        if (last < 0) return "";
        const first = data.findIndex((d) => d.model != null);
        return `${modelPath} L ${x(last)} ${padT + plotH} L ${x(first)} ${padT + plotH} Z`;
    }, [modelPath, data, H]);

    const active = hover != null ? data[hover] : null;

    return (
        <div className="relative">
            <svg
                viewBox={`0 0 ${W} ${H}`}
                className="w-full"
                style={{ height }}
                preserveAspectRatio="none"
                role="img"
                aria-label="Podium slots correct per round: model versus qualifying baseline"
            >
                <defs>
                    <linearGradient id="acc-fill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.30" />
                        <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0" />
                    </linearGradient>
                </defs>

                {/* gridlines */}
                {[0, 1, 2, 3].map((v) => (
                    <line
                        key={v}
                        x1={padL}
                        x2={W - padR}
                        y1={y(v)}
                        y2={y(v)}
                        stroke="var(--color-line)"
                        strokeWidth={1}
                        vectorEffect="non-scaling-stroke"
                    />
                ))}

                {areaPath && <path d={areaPath} fill="url(#acc-fill)" />}

                {/* baseline — dashed, recessive but always present */}
                {basePath && (
                    <path
                        d={basePath}
                        fill="none"
                        stroke="var(--color-fg-muted)"
                        strokeWidth={2}
                        strokeDasharray="7 6"
                        strokeLinecap="round"
                        vectorEffect="non-scaling-stroke"
                    />
                )}

                {/* model */}
                {modelPath && (
                    <path
                        d={modelPath}
                        fill="none"
                        stroke="var(--color-accent)"
                        strokeWidth={2.5}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        vectorEffect="non-scaling-stroke"
                    />
                )}

                {/* hover marker */}
                {active && active.model != null && hover != null && (
                    <>
                        <line
                            x1={x(hover)}
                            x2={x(hover)}
                            y1={padT}
                            y2={padT + plotH}
                            stroke="var(--color-line-strong)"
                            strokeWidth={1}
                            vectorEffect="non-scaling-stroke"
                        />
                        <circle
                            cx={x(hover)}
                            cy={y(active.model)}
                            r={5}
                            fill="var(--color-accent)"
                            stroke="var(--color-ink-2)"
                            strokeWidth={3}
                            vectorEffect="non-scaling-stroke"
                        />
                    </>
                )}

                {/* hit areas */}
                {data.map((d, i) => (
                    <rect
                        key={d.round}
                        x={x(i) - plotW / Math.max(pts - 1, 1) / 2}
                        y={padT}
                        width={plotW / Math.max(pts - 1, 1)}
                        height={plotH}
                        fill="transparent"
                        onMouseEnter={() => setHover(i)}
                        onMouseLeave={() => setHover(null)}
                    />
                ))}
            </svg>

            {/* y ticks, positioned outside the squashed viewBox */}
            <div
                className="absolute left-0 top-0 flex flex-col justify-between text-[10px] text-fg-subtle num pointer-events-none"
                style={{ height: height - 26, paddingTop: 6 }}
            >
                {[3, 2, 1, 0].map((v) => (
                    <span key={v}>{v}</span>
                ))}
            </div>

            {/* x labels */}
            <div className="flex justify-between mt-1 px-[26px]">
                {data.map((d, i) => (
                    <span
                        key={d.round}
                        className={`text-[10px] num transition-colors ${hover === i ? "text-fg" : "text-fg-subtle"
                            }`}
                    >
                        {d.label}
                    </span>
                ))}
            </div>

            {/* tooltip */}
            {active && (
                <div className="absolute top-2 right-2 rounded-lg bg-ink-4 border border-line px-3 py-2">
                    <p className="text-[11px] text-fg-muted mb-1">{active.label}</p>
                    <p className="text-[12px] text-fg num">
                        <span className="inline-block w-2 h-2 rounded-full bg-accent mr-1.5" />
                        model {active.model ?? "—"} / 3
                    </p>
                    <p className="text-[12px] text-fg-muted num">
                        <span className="inline-block w-2 h-[2px] bg-fg-muted mr-1.5 align-middle" />
                        grid {active.baseline ?? "—"} / 3
                    </p>
                </div>
            )}

            {/* legend */}
            <div className="flex items-center gap-5 mt-3">
                <span className="flex items-center gap-2 text-[11px] text-fg-muted">
                    <span className="w-4 h-[2.5px] rounded-full bg-accent" />
                    Model
                </span>
                <span className="flex items-center gap-2 text-[11px] text-fg-muted">
                    <svg width="18" height="3" aria-hidden>
                        <line
                            x1="0" y1="1.5" x2="18" y2="1.5"
                            stroke="var(--color-fg-muted)"
                            strokeWidth="2"
                            strokeDasharray="4 3"
                        />
                    </svg>
                    Qualifying baseline
                </span>
            </div>
        </div>
    );
}
