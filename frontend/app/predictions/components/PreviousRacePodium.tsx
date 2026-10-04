"use client";

import { motion } from "framer-motion";
import { resolveDriver, prettyName, TEAM_LOGOS } from "../../constants/drivers";

type PodiumEntry = {
    driverId: string;
    predictedPos: number | null; // What the model predicted for this driver
    probability: number | null;
};

type Props = {
    raceName: string;
    podium: [PodiumEntry, PodiumEntry, PodiumEntry] | PodiumEntry[];
    brierScore: number;
    correctCount: number;
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
        scale: "scale-95 z-10 md:scale-100 md:-translate-y-4",
        badge: "1",
        badgeColor: "#facc15",
        dropShadow: "group-hover:drop-shadow-[0_0_20px_rgba(255,215,0,0.9)]",
    },
    2: {
        glow: "#e5e7eb",
        glowRgba: "192,192,192",
        order: "md:order-1",
        scale: "scale-90 z-0 md:scale-90 md:translate-y-2",
        badge: "2",
        badgeColor: "#e5e7eb",
        dropShadow: "group-hover:drop-shadow-[0_0_20px_rgba(192,192,192,0.8)]",
    },
    3: {
        glow: "#d97706",
        glowRgba: "205,127,50",
        order: "md:order-3",
        scale: "scale-85 z-0 md:scale-85 md:translate-y-6",
        badge: "3",
        badgeColor: "#d97706",
        dropShadow: "group-hover:drop-shadow-[0_0_20px_rgba(205,127,50,0.9)]",
    },
};

function DriverColumn({ entry, position }: { entry: PodiumEntry; position: number }) {
    const d = resolveDriver(entry.driverId);
    const logo = d ? TEAM_LOGOS[d.team] : undefined;
    const style = CARD_STYLES[position];

    return (
        <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: position === 1 ? 0.1 : position === 2 ? 0 : 0.2, type: "spring", stiffness: 220, damping: 22 }}
            className={`group relative flex flex-col w-full md:w-[240px] rounded-xl overflow-hidden
                bg-[#111118] border border-white/10
                ${style.order} ${style.scale}
                transition-all duration-500 shadow-xl
                hover:-translate-y-1
                hover:shadow-[0_0_25px_rgba(${style.glowRgba},0.4)]
                hover:border-[rgba(${style.glowRgba},0.4)]`}
        >
            {/* Top Layout (Badge & Logo) */}
            <div className="absolute top-8 left-0 w-full px-5 flex justify-between items-center z-20 pointer-events-none">
                {/* Position badge */}
                <div
                    className="w-7 h-7 rounded-full flex items-center justify-center font-black text-black shadow-[0_0_15px_rgba(0,0,0,0.5)] text-xs"
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
                        className="w-10 h-10 object-contain brightness-0 invert opacity-70 drop-shadow-md"
                    />
                )}
            </div>

            {/* Driver Cutout & Large Shadow Text */}
            <div className="relative h-[220px] w-full flex items-end justify-center overflow-hidden bg-gradient-to-t from-[#1a1a24] via-transparent to-transparent">
                {/* Large faint background position text */}
                <div
                    className="absolute top-2 left-5 font-black italic text-6xl opacity-10 pointer-events-none select-none transition-opacity duration-500 group-hover:opacity-20"
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
                            <div className="w-full h-full flex items-center justify-center text-white/10 text-5xl">👤</div>
                        )}
                    </div>
                </div>
            </div>

            {/* Info Footer */}
            <div className="relative z-20 bg-[#1a1a24] p-4 text-center border-t border-white/5">
                <p
                    className="text-[17px] font-black text-white italic tracking-wide uppercase leading-tight transition-colors duration-300"
                    style={{ textShadow: `0 0 0px ${style.glow}00` }}
                    onMouseEnter={(e) => (e.currentTarget.style.textShadow = `0 0 12px ${style.glow}90`)}
                    onMouseLeave={(e) => (e.currentTarget.style.textShadow = `0 0 0px ${style.glow}00`)}
                >
                    {d?.name ?? prettyName(entry.driverId)}
                </p>
                <div className="flex items-center justify-center gap-2 mt-1.5">
                    <span className="text-[10px] text-white/50 uppercase tracking-[0.2em] font-bold">
                        {d?.team ?? "—"}
                    </span>
                </div>
                <div className="mt-3 pt-3 border-t border-white/5 flex items-center justify-between px-1">
                    <div className="flex flex-col text-left">
                        <span className="text-[9px] text-white/40 uppercase tracking-widest font-bold mb-0.5">Predicted</span>
                        {entry.predictedPos === position ? (
                            <span className="text-[11px] font-black text-emerald-400">CORRECT (P{position})</span>
                        ) : entry.predictedPos ? (
                            <span className="text-[11px] font-black text-red-400">P{entry.predictedPos}</span>
                        ) : (
                            <span className="text-[11px] font-black text-white/30">UNPLACED</span>
                        )}
                    </div>
                    {entry.probability != null && (
                        <div className="flex flex-col text-right">
                            <span className="text-[9px] text-white/40 uppercase tracking-widest font-bold mb-0.5">Win Prob</span>
                            <span className="text-[12px] font-mono font-bold text-accent">
                                {(entry.probability * 100).toFixed(1)}%
                            </span>
                        </div>
                    )}
                </div>
            </div>
        </motion.div>
    );
}

export default function PreviousRacePodium({ raceName, podium, correctCount, brierScore }: Props) {
    const [p1, p2, p3] = podium;
    if (!p1 || !p2 || !p3) return null;

    return (
        <section className="relative overflow-visible p-4 md:p-6 mb-8">
            <div className="relative text-center mb-8">
                <p className="text-xs mb-2 text-accent uppercase tracking-widest font-bold">Previous Race</p>
                <h2 className="text-2xl font-black italic text-white uppercase tracking-wider">{raceName}</h2>
                <div className="flex justify-center mt-3">
                    <div className={`px-4 py-1.5 rounded-full text-[11px] uppercase tracking-widest font-black ${correctCount === 3 ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : correctCount >= 2 ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : correctCount >= 1 ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                        {correctCount}/3 Predicted Correctly · Brier: {brierScore.toFixed(3)}
                    </div>
                </div>
            </div>

            <div className="relative flex flex-col md:flex-row items-center md:items-start justify-center gap-4 md:gap-3 md:h-[380px] pt-4">
                <DriverColumn entry={p2} position={2} />
                <DriverColumn entry={p1} position={1} />
                <DriverColumn entry={p3} position={3} />
            </div>
        </section>
    );
}
