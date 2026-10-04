"use client";

import { motion } from "framer-motion";

import { resolveDriver, prettyName, TEAM_LOGOS } from "../../constants/drivers";

type PodiumEntry = {
    driverId: string;
    probability: number | null;
};

type Props = {
    raceName: string;
    podium: [PodiumEntry, PodiumEntry, PodiumEntry] | PodiumEntry[];
};

const CARD_STYLES: Record<number, {
    glow: string;
    glowRgba: string;
    order: string;
    scale: string;
    badge: string;
    badgeColor: string;
    dropShadow: string;
}> = {
    1: {
        glow: "#facc15",
        glowRgba: "255,215,0",
        order: "md:order-2",
        scale: "scale-100 z-10 md:scale-110 md:-translate-y-6",
        badge: "1",
        badgeColor: "#facc15",
        dropShadow: "group-hover:drop-shadow-[0_0_24px_rgba(255,215,0,0.9)]",
    },
    2: {
        glow: "#e5e7eb",
        glowRgba: "192,192,192",
        order: "md:order-1",
        scale: "scale-95 z-0 md:scale-100 md:translate-y-4",
        badge: "2",
        badgeColor: "#e5e7eb",
        dropShadow: "group-hover:drop-shadow-[0_0_24px_rgba(192,192,192,0.8)]",
    },
    3: {
        glow: "#d97706",
        glowRgba: "205,127,50",
        order: "md:order-3",
        scale: "scale-90 z-0 md:scale-95 md:translate-y-8",
        badge: "3",
        badgeColor: "#d97706",
        dropShadow: "group-hover:drop-shadow-[0_0_24px_rgba(205,127,50,0.9)]",
    },
};

function DriverColumn({ entry, position }: { entry: PodiumEntry; position: number }) {
    const d = resolveDriver(entry.driverId);
    const logo = d ? TEAM_LOGOS[d.team] : undefined;
    const style = CARD_STYLES[position];

    return (
        <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: position === 1 ? 0.15 : position === 2 ? 0 : 0.3, type: "spring", stiffness: 220, damping: 22 }}
            className={`group relative flex flex-col w-full md:w-[280px] rounded-xl overflow-hidden
                bg-[#111118] border border-white/10
                ${style.order} ${style.scale}
                transition-all duration-500 shadow-2xl
                hover:-translate-y-2
                hover:shadow-[0_0_30px_rgba(${style.glowRgba},0.5)]
                hover:border-[rgba(${style.glowRgba},0.4)]`}
        >
            {/* Top Layout (Badge & Logo) */}
            <div className="absolute top-12 left-0 w-full px-6 flex justify-between items-center z-20 pointer-events-none">
                {/* Position badge */}
                <div
                    className="w-8 h-8 rounded-full flex items-center justify-center font-black text-black shadow-[0_0_15px_rgba(0,0,0,0.5)] text-sm"
                    style={{ backgroundColor: style.badgeColor }}
                >
                    {style.badge}
                </div>
                {/* Team Logo */}
                {logo && (
                    <img
                        src={logo}
                        alt=""
                        aria-hidden
                        className="w-12 h-12 object-contain brightness-0 invert opacity-70 drop-shadow-md"
                    />
                )}
            </div>

            {/* Driver Cutout & Large Shadow Text */}
            <div className="relative h-[260px] w-full flex items-end justify-center overflow-hidden bg-gradient-to-t from-[#1a1a24] via-transparent to-transparent">
                {/* Large faint background position text */}
                <div
                    className="absolute top-4 left-6 font-black italic text-7xl opacity-10 pointer-events-none select-none transition-opacity duration-500 group-hover:opacity-20"
                    style={{ color: style.glow }}
                >
                    P{position}
                </div>

                {/* Driver cutout image */}
                <div className="absolute inset-0 flex items-end justify-center">
                    <div className="relative w-full h-full transform transition-transform duration-700 group-hover:scale-105">
                        {d?.img ? (
                            <img
                                src={d.img}
                                alt={d.name}
                                className={`absolute inset-0 w-full h-full object-cover object-top transition-all duration-500 drop-shadow-lg ${style.dropShadow}`}
                            />
                        ) : (
                            <div className="w-full h-full flex items-center justify-center text-white/10 text-6xl">👤</div>
                        )}
                    </div>
                </div>
            </div>

            {/* Info Footer */}
            <div className="relative z-20 bg-[#1a1a24] p-5 text-center border-t border-white/5">
                <p
                    className="text-[19px] font-black text-white italic tracking-wide uppercase leading-tight transition-colors duration-300"
                    style={{ textShadow: `0 0 0px ${style.glow}00` }}
                    onMouseEnter={(e) => (e.currentTarget.style.textShadow = `0 0 14px ${style.glow}90`)}
                    onMouseLeave={(e) => (e.currentTarget.style.textShadow = `0 0 0px ${style.glow}00`)}
                >
                    {d?.name ?? prettyName(entry.driverId)}
                </p>
                <div className="flex items-center justify-center gap-2 mt-2">
                    <span className="text-[11px] text-white/50 uppercase tracking-[0.2em] font-bold">
                        {d?.team ?? "—"}
                    </span>
                </div>
                {entry.probability != null && (
                    <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between px-2">
                        <span className="text-[10px] text-white/40 uppercase tracking-widest font-bold">Win Prob</span>
                        <span className="text-[13px] font-mono font-bold text-accent">
                            {(entry.probability * 100).toFixed(1)}%
                        </span>
                    </div>
                )}
            </div>
        </motion.div>
    );
}

export default function PodiumStage({ raceName, podium }: Props) {
    const [p1, p2, p3] = podium;
    if (!p1 || !p2 || !p3) return null;

    return (
        <section className="relative overflow-visible p-4 md:p-8 pt-12 md:pt-16 mb-12 mt-6">
            <div className="relative text-center mb-12">
                <p className="text-xs mb-2 text-accent uppercase tracking-widest font-bold">Prediction engine · complete</p>
                <h2 className="text-3xl font-black italic text-white uppercase tracking-wider">{raceName}</h2>
            </div>

            <div className="relative flex flex-col md:flex-row items-center md:items-start justify-center gap-6 md:gap-4 md:h-[460px] pt-8">
                <DriverColumn entry={p2} position={2} />
                <DriverColumn entry={p1} position={1} />
                <DriverColumn entry={p3} position={3} />
            </div>
        </section>
    );
}
