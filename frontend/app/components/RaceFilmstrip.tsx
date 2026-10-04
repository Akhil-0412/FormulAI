"use client";

import { Calendar, MapPin, Check } from "lucide-react";
import { Badge } from "./ui/Primitives";

/**
 * 20 / 60 / 20 race filmstrip.
 *
 * The previous and upcoming races sit half-lit at the edges so the
 * season reads as a sequence rather than a single isolated event, while
 * the next race keeps the visual weight. The flanking panels are dimmed
 * and slightly desaturated rather than shrunk, which keeps the three
 * baselines aligned.
 */

export type RaceCard = {
    round: number;
    name: string;
    circuit?: string;
    dateString: string;
    /** Winner or podium line for a completed race. */
    result?: string;
};

type Props = {
    previous?: RaceCard | null;
    next: RaceCard;
    upcoming?: RaceCard | null;
    countdown: { days: number; hours: number; minutes: number; seconds: number };
};

const bgImages: Record<string, string> = {
    "Dutch Grand Prix": "/images/races/dutch_gp.jpg",
    "Italian Grand Prix": "/images/races/italian_gp.jpg",
    "Spanish Grand Prix": "/images/races/spanish_gp.jpg",
    "Australian Grand Prix": "/images/races/melbourne_gp.jpg",
    "Chinese Grand Prix": "/images/races/shanghai_gp.jpg",
    "Japanese Grand Prix": "/images/races/suzuka_gp.jpg",
};

// Fallbacks if we don't have a mapped image
const getBg = (name: string, fallbackIndex: number) => {
    if (bgImages[name]) return bgImages[name];
    const fallbacks = [
        "/images/races/dutch_gp.jpg",
        "/images/races/italian_gp.jpg",
        "/images/races/spanish_gp.jpg",
        "/images/races/melbourne_gp.jpg",
        "/images/races/shanghai_gp.jpg",
        "/images/races/suzuka_gp.jpg",
    ];
    return fallbacks[fallbackIndex % fallbacks.length];
};

function Flank({
    race,
    side,
    tone,
}: {
    race: RaceCard;
    side: "left" | "right";
    tone: "past" | "future";
}) {
    // For now use a deterministic fallback so they don't all look the same if unmapped
    const bgUrl = getBg(race.name, tone === "past" ? 0 : 2);

    return (
        <div
            className={`hidden lg:flex flex-col justify-between w-[20%] shrink-0 p-5
                        relative overflow-hidden group border border-line ${side === "left"
                    ? "rounded-l-[var(--radius-card)] border-r-0"
                    : "rounded-r-[var(--radius-card)] border-l-0"
                }`}
        >
            {/* Background Image */}
            <div 
                className="absolute inset-0 bg-cover bg-center transition-transform duration-700 group-hover:scale-105"
                style={{ backgroundImage: `url('${bgUrl}')` }}
            />
            {/* Overlays for readability and UI depth */}
            <div className="absolute inset-0 bg-ink-1/80 mix-blend-multiply" />
            <div className="absolute inset-0 bg-gradient-to-t from-ink-1 via-ink-1/50 to-transparent" />
            <div className="absolute inset-0 bg-ink-2/40 group-hover:bg-transparent transition-colors duration-500" />

            <div className="relative z-10">
                <p className="label-xs mb-2">
                    {tone === "past" ? "Previous" : "Upcoming"}
                </p>
                <p className="text-[13px] font-semibold text-fg leading-snug line-clamp-2">
                    {race.name}
                </p>
                <p className="text-[11px] text-fg-subtle mt-1 num">
                    R{String(race.round).padStart(2, "0")} · {race.dateString}
                </p>
            </div>

            <div className="relative z-10 mt-4">
                {tone === "past" ? (
                    race.result ? (
                        <div className="flex items-center gap-1.5 text-[11px] text-fg-subtle">
                            <Check className="w-3 h-3 shrink-0 text-good" strokeWidth={2.5} />
                            <span className="truncate" title={race.result}>
                                {race.result}
                            </span>
                        </div>
                    ) : (
                        <span className="text-[11px] text-fg-subtle">Result pending</span>
                    )
                ) : (
                    <span className="text-[11px] text-fg-subtle">Scheduled</span>
                )}
            </div>
        </div>
    );
}

export default function RaceFilmstrip({
    previous,
    next,
    upcoming,
    countdown,
}: Props) {
    const units = [
        { v: countdown.days, l: "Days" },
        { v: countdown.hours, l: "Hrs" },
        { v: countdown.minutes, l: "Min" },
        { v: countdown.seconds, l: "Sec" },
    ];

    const nextBgUrl = getBg(next.name, 1);

    return (
        <section className="flex items-stretch" aria-label="Race sequence">
            {previous ? (
                <Flank race={previous} side="left" tone="past" />
            ) : (
                <div className="hidden lg:block w-[20%] shrink-0" />
            )}

            {/* Centre — the next race */}
            <div
                className="w-full lg:w-[60%] shrink-0 relative overflow-hidden group
                           rounded-[var(--radius-card)] bg-ink-2 border border-line-strong
                           p-6 sm:p-8 z-10"
            >
                {/* Background Image */}
                <div 
                    className="absolute inset-0 bg-cover bg-center transition-transform duration-1000 group-hover:scale-105"
                    style={{ backgroundImage: `url('${nextBgUrl}')` }}
                />
                
                {/* Cinematic Overlays */}
                <div className="absolute inset-0 bg-ink-2/50 mix-blend-multiply" />
                <div className="absolute inset-0 bg-gradient-to-r from-ink-1/95 via-ink-1/70 to-transparent" />
                <div className="absolute inset-0 bg-gradient-to-t from-ink-1/80 via-transparent to-transparent" />

                {/* A single soft red bloom anchored behind the title. */}
                <div
                    className="absolute -top-24 -left-16 w-[420px] h-[420px] rounded-full
                               pointer-events-none opacity-[0.25] mix-blend-screen"
                    style={{
                        background:
                            "radial-gradient(circle, var(--color-accent) 0%, transparent 60%)",
                    }}
                />

                <div className="relative z-10">
                    <div className="flex items-center gap-2.5 mb-5 flex-wrap">
                        <Badge tone="live">Next race</Badge>
                        <span className="label-xs text-white/90">
                            Round {String(next.round).padStart(2, "0")}
                        </span>
                    </div>

                    <h1 className="h-display text-white mb-3 text-balance drop-shadow-md">{next.name}</h1>

                    <div className="flex items-center gap-4 flex-wrap text-[13px] text-white/80 mb-7">
                        <span className="flex items-center gap-1.5 drop-shadow-sm">
                            <Calendar className="w-3.5 h-3.5" strokeWidth={2} />
                            {next.dateString}
                        </span>
                        {next.circuit && (
                            <span className="flex items-center gap-1.5 drop-shadow-sm">
                                <MapPin className="w-3.5 h-3.5" strokeWidth={2} />
                                {next.circuit}
                            </span>
                        )}
                    </div>

                    {/* Countdown */}
                    <div className="flex items-end gap-2 sm:gap-3 drop-shadow-md">
                        <p className="label-xs text-white/90 mb-2 mr-1 hidden sm:block">Lights out in</p>
                        {units.map((u, i) => (
                            <div key={u.l} className="flex items-end gap-2 sm:gap-3">
                                <div className="text-center">
                                    <div
                                        className={`text-[30px] sm:text-[38px] font-bold leading-none num tracking-[-0.03em] ${
                                            u.l === "Sec" ? "text-accent drop-shadow-[0_0_10px_rgba(232,0,32,0.4)]" : "text-white"
                                        }`}
                                    >
                                        {String(u.v).padStart(2, "0")}
                                    </div>
                                    <div className="text-[10px] text-white/70 mt-1.5 tracking-wide">
                                        {u.l}
                                    </div>
                                </div>
                                {i < units.length - 1 && (
                                    <span className="text-[26px] text-white/50 leading-none mb-4">
                                        :
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {upcoming ? (
                <Flank race={upcoming} side="right" tone="future" />
            ) : (
                <div className="hidden lg:block w-[20%] shrink-0" />
            )}
        </section>
    );
}
