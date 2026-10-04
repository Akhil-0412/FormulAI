"use client";

import { resolveDriver } from "../../constants/drivers";

/**
 * Driver portrait.
 *
 * Every asset (2025 intake and the 2026 arrivals alike — Hadjar, Lindblad,
 * Hülkenberg, Bortoleto, Bottas, Pérez, Sainz) is the same 440×1375
 * full-body cutout render, confirmed by scanning pixel content: figure
 * spans roughly 1–95% of the frame height in every file, head centred
 * around 30–66% of the width. There's no actual format difference between
 * the "partial reveal" and regular assets, so one crop works for all of
 * them — a `partialReveal` branch here would be solving a problem that
 * doesn't exist in the source images.
 *
 * The crop: object-fit cover pins the image to the box width (440 is the
 * limiting dimension), then object-position "50% 0%" top-aligns it, showing
 * the top 32% of the figure (top / (box/imgWidth) = imgHeight-equivalent).
 * A further scale(1.8) from a top-center transform-origin narrows that to
 * the top ~18% vertically and the center ~56% horizontally — measured
 * against the actual head/shoulder bounding box in the source art, not
 * eyeballed.
 */
const CROP_SCALE = 1.8;

type Props = {
    driverKey: string;
    size?: number;
    /** Show a coloured ring in the team colour. */
    ring?: boolean;
    className?: string;
};

export default function DriverAvatar({
    driverKey,
    size = 36,
    ring = false,
    className = "",
}: Props) {
    const d = resolveDriver(driverKey);

    if (!d) {
        return (
            <div
                className={`rounded-full bg-ink-4 grid place-items-center shrink-0 ${className}`}
                style={{ width: size, height: size }}
                aria-hidden
            >
                <span
                    className="font-bold text-fg-subtle"
                    style={{ fontSize: size * 0.34 }}
                >
                    {driverKey.slice(0, 2).toUpperCase()}
                </span>
            </div>
        );
    }

    // The ring is a solid circle painted BEHIND the photo, not an inset
    // box-shadow drawn on top of it — an inset shadow overlaps the outer
    // 2px of the portrait itself (cutting into the driver's face at the
    // crop edge); a separate back layer shows the ring colour only in the
    // rim the photo doesn't cover.
    return (
        <div
            className={`relative shrink-0 ${className}`}
            style={{ width: size, height: size }}
            title={d.name}
        >
            {ring && (
                <div
                    className="absolute inset-0 rounded-full"
                    style={{ backgroundColor: d.color }}
                    aria-hidden
                />
            )}
            <div
                className="absolute rounded-full overflow-hidden bg-ink-4"
                style={{ inset: ring ? 2 : 0 }}
            >
                {/* Plain <img> rather than next/image: these are small local
                    AVIFs served straight from /public, so the optimiser is
                    bypassed anyway, and `fill` fights the transform used to
                    re-frame the portraits. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                    src={d.img}
                    alt={d.name}
                    // Eager: avatars are tiny and sit in the initial viewport,
                    // so lazy-loading only delays them behind the fold check.
                    loading="eager"
                    decoding="async"
                    className="absolute inset-0 w-full h-full object-cover"
                    style={{
                        objectPosition: "50% 0%",
                        transform: `scale(${CROP_SCALE})`,
                        transformOrigin: "50% 0%",
                    }}
                />
            </div>
        </div>
    );
}
