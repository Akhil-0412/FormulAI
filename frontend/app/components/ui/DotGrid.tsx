"use client";

/**
 * Monte Carlo outcome grid.
 *
 * The reference uses a row of dots as a status ornament. Here each dot
 * is one bucket of simulated races, so the fill level *is* the podium
 * probability — a reader can count the filled dots and get the number.
 * Stage 3 already runs 10,000 draws; this makes them legible.
 */

type Props = {
    /** Probability in [0, 1]. */
    probability: number;
    /** Total dots. 25 reads cleanly and each dot is a tidy 4%. */
    total?: number;
    label?: string;
};

export default function DotGrid({ probability, total = 25, label }: Props) {
    const p = Math.max(0, Math.min(1, probability || 0));
    const filled = Math.round(p * total);

    return (
        <div>
            <div
                className="flex flex-wrap gap-[5px]"
                role="img"
                aria-label={
                    label ??
                    `${Math.round(p * 100)} percent of simulations end on the podium`
                }
            >
                {Array.from({ length: total }).map((_, i) => {
                    const isFilled = i < filled;
                    // The dot straddling the boundary is drawn as an outline,
                    // so a 41% and a 44% don't render identically.
                    const isEdge = i === filled && p * total - filled > 0.25;
                    return (
                        <span
                            key={i}
                            className="w-[7px] h-[7px] rounded-full shrink-0"
                            style={{
                                backgroundColor: isFilled
                                    ? "var(--color-accent)"
                                    : "transparent",
                                border: isFilled
                                    ? "none"
                                    : `1px solid ${isEdge
                                        ? "var(--color-accent-dim)"
                                        : "var(--color-line-strong)"
                                    }`,
                            }}
                        />
                    );
                })}
            </div>
        </div>
    );
}
