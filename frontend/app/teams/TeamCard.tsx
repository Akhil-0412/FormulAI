"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Trophy, ChevronDown, ChevronUp, Info, MapPin } from "lucide-react";
import DriverAvatar from "../components/ui/DriverAvatar";
import { resolveDriver, prettyName } from "../constants/drivers";

type Team = {
    name: string;
    chassis: string;
    drivers: string[];
    logoPath: string | null;
    carPath: string | null;
    color: string;
    stats: {
        wins: number;
        championships: number;
        trackRecord: string;
        recentWins: string[];
    };
};

export default function TeamCard({ team }: { team: Team }) {
    const [isExpanded, setIsExpanded] = useState(false);

    return (
        // `layout` (not a CSS transition) is what makes this smooth. Grid
        // span changes (col-span-2/row-span-2) aren't a continuously
        // interpolable CSS value — every browser snaps them instantly no
        // matter what `transition` property lists, which is why this used
        // to jump. `layout` measures this card's rect before and after the
        // span change and animates a transform between them (FLIP), and
        // because every card in the grid carries the same prop, the
        // siblings that get pushed around by the resize animate their own
        // reflow too, instead of snapping to their new slot.
        <motion.div
            layout
            transition={{ type: "spring", stiffness: 300, damping: 32 }}
            className={`card card-interactive flex flex-col overflow-hidden cursor-pointer group
                        ${isExpanded ? "md:col-span-2 xl:col-span-2 row-span-2" : ""}`}
            style={{ borderTop: `3px solid ${team.color}` }}
            onClick={() => setIsExpanded((v) => !v)}
            role="button"
            aria-expanded={isExpanded}
        >
            <div className="p-5">
                {/* Header / Logo */}
                <div className="flex justify-between items-start mb-5">
                    <div>
                        <h3 className="h-card text-fg uppercase tracking-tight">{team.name}</h3>
                        <p className="label-xs mt-1">{team.chassis}</p>
                    </div>
                    {team.logoPath && (
                        <div className="relative w-12 h-12 shrink-0 transition-transform group-hover:scale-110 duration-300">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                                src={team.logoPath}
                                alt=""
                                aria-hidden
                                className="absolute inset-0 w-full h-full object-contain"
                            />
                        </div>
                    )}
                </div>

                {/* Car (always visible) */}
                <div className="flex items-center justify-center relative mb-5">
                    {team.carPath ? (
                        <div
                            className={`relative w-full transition-all duration-500 ${isExpanded ? "h-[220px] scale-105" : "h-[110px] group-hover:scale-105"
                                }`}
                        >
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                                src={team.carPath}
                                alt={`${team.name} car`}
                                className="absolute inset-0 w-full h-full object-contain drop-shadow-xl"
                            />
                        </div>
                    ) : (
                        <div
                            className={`text-center opacity-30 flex flex-col justify-center ${isExpanded ? "h-[220px]" : "h-[110px]"
                                }`}
                        >
                            <span className="text-[11px] font-semibold tracking-widest uppercase text-fg-subtle">
                                Awaiting asset
                            </span>
                        </div>
                    )}
                </div>

                {/* Expanded detail */}
                <div
                    className={`transition-all duration-500 ease-in-out ${isExpanded ? "max-h-[600px] opacity-100 mt-6" : "max-h-0 opacity-0 overflow-hidden"
                        }`}
                >
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 border-t border-line pt-6">
                        {/* Stats */}
                        <div className="flex flex-col gap-4">
                            <h4 className="text-[13px] font-bold text-fg flex items-center gap-2">
                                <Trophy className="w-4 h-4 text-warn" /> Team statistics
                            </h4>

                            <div className="grid grid-cols-2 gap-3">
                                <div className="card-raised p-3.5 relative group/stat">
                                    <p className="label-xs mb-1.5">Total wins</p>
                                    <p className="text-[26px] font-bold text-fg leading-none">{team.stats.wins}</p>

                                    <div
                                        className="absolute left-0 bottom-full mb-2 w-52 p-3 rounded-lg bg-ink-4
                                                   border border-line shadow-2xl opacity-0
                                                   group-hover/stat:opacity-100 transition-opacity
                                                   pointer-events-none z-10 flex flex-col gap-1.5"
                                    >
                                        <p className="text-[10px] font-bold text-warn uppercase tracking-wide">
                                            Notable wins
                                        </p>
                                        {team.stats.recentWins.map((win, i) => (
                                            <p key={i} className="text-fg text-[11px] truncate">
                                                {win}
                                            </p>
                                        ))}
                                    </div>
                                </div>

                                <div className="card-raised p-3.5">
                                    <p className="label-xs mb-1.5">Championships</p>
                                    <p className="text-[26px] font-bold text-fg leading-none">
                                        {team.stats.championships}
                                    </p>
                                </div>
                            </div>

                            <div className="card-raised p-3.5">
                                <p className="label-xs mb-2 flex items-center gap-1.5">
                                    <MapPin className="w-3.5 h-3.5" /> Track record
                                </p>
                                <p className="text-[12.5px] text-fg-muted leading-relaxed">
                                    {team.stats.trackRecord}
                                </p>
                            </div>
                        </div>

                        {/* Drivers */}
                        <div className="flex flex-col gap-4">
                            <h4 className="text-[13px] font-bold text-fg flex items-center gap-2">
                                <Info className="w-4 h-4 text-warn" /> 2026 lineup
                            </h4>

                            <div className="flex flex-col gap-2.5">
                                {team.drivers.map((code, idx) => {
                                    const d = resolveDriver(code);
                                    return (
                                        <div
                                            key={code}
                                            className="card-raised flex items-center gap-3 p-3"
                                        >
                                            <DriverAvatar driverKey={code} size={48} ring />
                                            <div className="flex flex-col min-w-0">
                                                <p className="text-[14px] font-semibold text-fg truncate">
                                                    {d?.name ?? prettyName(code)}
                                                </p>
                                                <p className="label-xs mt-0.5">Seat {idx + 1}</p>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Collapsed driver chips */}
                {!isExpanded && (
                    <div className="flex justify-end gap-2 mt-2 pt-4 border-t border-line">
                        {team.drivers.map((code) => {
                            const d = resolveDriver(code);
                            return (
                                <div
                                    key={code}
                                    className="flex items-center gap-2 pl-1.5 pr-3 py-1.5 rounded-full
                                               bg-ink-3 border border-line text-[12px] font-semibold text-fg-muted"
                                >
                                    <DriverAvatar driverKey={code} size={22} />
                                    {d?.code ?? code}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            <div
                className={`w-full text-center py-2 bg-ink-3 border-t border-line text-fg-subtle
                            group-hover:text-fg transition-colors ${isExpanded ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                    }`}
            >
                {isExpanded ? (
                    <ChevronUp className="w-4 h-4 mx-auto" />
                ) : (
                    <ChevronDown className="w-4 h-4 mx-auto" />
                )}
            </div>
        </motion.div>
    );
}
