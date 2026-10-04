"use client";

/**
 * Overlapping avatar stack with an overflow count.
 *
 * Avatars carry a ring in the surface colour rather than a border, so
 * they separate where they overlap without adding ink that isn't data.
 */

type Props = {
    /** How many avatar slots to render. */
    count?: number;
    /** Number shown in the "+N" pill. Omit or pass 0 to hide it. */
    overflow?: number;
    /** Optional real image sources; falls back to initial-less placeholders. */
    srcs?: string[];
    size?: number;
};

export default function AvatarCluster({
    count = 4,
    overflow = 0,
    srcs,
    size = 26,
}: Props) {
    const slots = Array.from({ length: count });

    return (
        <div className="flex items-center">
            {slots.map((_, i) => (
                <div
                    key={i}
                    className="rounded-full bg-ink-4 ring-2 ring-ink-2 overflow-hidden shrink-0"
                    style={{
                        width: size,
                        height: size,
                        marginLeft: i === 0 ? 0 : -size * 0.32,
                        zIndex: count - i,
                    }}
                >
                    {srcs?.[i] ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                            src={srcs[i]}
                            alt=""
                            className="w-full h-full object-cover object-top"
                        />
                    ) : (
                        <div className="w-full h-full bg-gradient-to-br from-ink-4 to-ink-3" />
                    )}
                </div>
            ))}

            {overflow > 0 && (
                <div
                    className="rounded-full bg-accent text-white grid place-items-center
                               ring-2 ring-ink-2 shrink-0 num"
                    style={{
                        width: size,
                        height: size,
                        marginLeft: -size * 0.32,
                        fontSize: size * 0.36,
                        fontWeight: 700,
                    }}
                >
                    +{overflow}
                </div>
            )}
        </div>
    );
}
