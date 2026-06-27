'use client';
import { useState } from 'react';
import Image from 'next/image';
import { Trophy, ChevronDown, ChevronUp, Info, MapPin } from "lucide-react";

export default function TeamCard({ team }: { team: any }) {
    const [isExpanded, setIsExpanded] = useState(false);

    return (
        <div
            className={`glass-card flex flex-col justify-between transition-all duration-500 overflow-hidden cursor-pointer group hover:-translate-y-1 ${isExpanded ? 'col-span-1 md:col-span-2 xl:col-span-2 row-span-2' : ''} border-t-[4px] ${team.border}`}
            onClick={() => setIsExpanded(!isExpanded)}
        >
            <div className="p-6">
                {/* Header / Logo */}
                <div className="flex justify-between items-start mb-6">
                    <div>
                        <h3 className="text-2xl font-black text-white italic tracking-tighter uppercase mb-1">{team.name}</h3>
                        <p className="text-sm font-bold tracking-widest text-f1-muted uppercase">{team.chassis}</p>
                    </div>
                    {team.logoPath && (
                        <div className="relative w-16 h-16 transform transition-transform group-hover:scale-110 duration-500">
                            <Image src={team.logoPath} alt={`${team.name} Logo`} fill className="object-contain" unoptimized />
                        </div>
                    )}
                </div>

                {/* Car Image (Always Visible) */}
                <div className="flex-1 flex items-center justify-center relative mb-6">
                    {team.carPath ? (
                        <div className={`relative w-full transform transition-all duration-700 ${isExpanded ? 'h-[250px] scale-110 drop-shadow-2xl' : 'h-[120px] group-hover:scale-105'}`}>
                            <Image src={team.carPath} alt={`${team.name} Car`} fill className="object-contain drop-shadow-xl" priority unoptimized />
                        </div>
                    ) : (
                        <div className={`text-center opacity-30 ${isExpanded ? 'h-[250px] flex flex-col justify-center' : 'h-[120px] flex flex-col justify-center'}`}>
                            <span className="text-5xl block mb-2">🖼️</span>
                            <span className="text-sm font-semibold tracking-widest uppercase">Awaiting Asset</span>
                        </div>
                    )}
                </div>

                {/* Expanded Details */}
                <div className={`transition-all duration-700 ease-in-out ${isExpanded ? 'max-h-[500px] opacity-100 mt-8' : 'max-h-0 opacity-0 overflow-hidden'}`}>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8 border-t border-white/10 pt-8">

                        {/* Column 1: Stats */}
                        <div className="flex flex-col gap-6">
                            <h4 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
                                <Trophy className="w-5 h-5 text-f1-papaya" /> Team Statistics
                            </h4>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="glass-panel p-4 rounded-xl border border-white/5 relative group/stat">
                                    <p className="text-f1-muted text-xs font-bold uppercase tracking-widest mb-1">Total Wins</p>
                                    <p className="text-3xl font-black text-white">{team.stats.wins}</p>

                                    {/* Hover Tooltip for Recent Wins */}
                                    <div className="absolute left-0 bottom-full mb-2 w-48 p-3 rounded-lg bg-f1-navy border border-white/10 shadow-2xl opacity-0 group-hover/stat:opacity-100 transition-opacity pointer-events-none z-10 flex flex-col gap-2">
                                        <p className="text-xs font-bold text-f1-papaya uppercase">Notable Wins</p>
                                        {team.stats.recentWins.map((win: string, i: number) => (
                                            <p key={i} className="text-white text-xs truncate">- {win}</p>
                                        ))}
                                    </div>
                                </div>

                                <div className="glass-panel p-4 rounded-xl border border-white/5">
                                    <p className="text-f1-muted text-xs font-bold uppercase tracking-widest mb-1">Championships</p>
                                    <p className="text-3xl font-black text-white">{team.stats.championships}</p>
                                </div>
                            </div>

                            <div className="glass-panel p-4 rounded-xl border border-white/5 mt-2">
                                <p className="text-f1-muted text-xs font-bold uppercase tracking-widest mb-2 flex items-center gap-2">
                                    <MapPin className="w-4 h-4" /> Track Record
                                </p>
                                <p className="text-sm text-white/80 leading-relaxed font-medium">{team.stats.trackRecord}</p>
                            </div>
                        </div>

                        {/* Column 2: Drivers */}
                        <div className="flex flex-col gap-6">
                            <h4 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
                                <Info className="w-5 h-5 text-f1-papaya" /> 2026 Lineup
                            </h4>

                            <div className="flex flex-col gap-4">
                                {[{ name: team.drivers[0], path: team.drv1Path }, { name: team.drivers[1], path: team.drv2Path }].map((drv, idx) => (
                                    <div key={idx} className="flex items-center gap-4 p-4 rounded-xl bg-white/5 border border-white/10 backdrop-blur-sm group-hover:bg-white/10 transition-colors">
                                        {drv.path ? (
                                            <div className="w-16 h-16 rounded-full overflow-hidden relative border-2 border-white/10">
                                                <Image src={drv.path} alt={drv.name} fill className="object-cover object-top" unoptimized />
                                            </div>
                                        ) : (
                                            <div className="w-16 h-16 rounded-full bg-white/10 flex items-center justify-center text-2xl">👤</div>
                                        )}
                                        <div className="flex flex-col">
                                            <p className="text-lg font-black text-white italic tracking-tighter uppercase">{drv.name}</p>
                                            <p className="text-xs font-bold text-f1-muted tracking-widest uppercase">Seat {idx + 1}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                    </div>
                </div>

                {/* Collapsed view drivers */}
                {!isExpanded && (
                    <div className="flex justify-end gap-2 mt-auto pt-6 border-t border-white/5 animate-in fade-in zoom-in duration-300">
                        {[{ name: team.drivers[0], path: team.drv1Path }, { name: team.drivers[1], path: team.drv2Path }].map((drv, idx) => (
                            <div key={idx} className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 backdrop-blur-sm text-sm font-semibold text-white/90">
                                {drv.path && (
                                    <div className="w-6 h-6 rounded-full overflow-hidden relative">
                                        <Image src={drv.path} alt={drv.name} fill className="object-cover object-top" unoptimized />
                                    </div>
                                )}
                                {drv.name}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div className={`w-full text-center py-2 bg-white/5 border-t border-white/5 text-f1-muted group-hover:text-white transition-colors ${isExpanded ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
                {isExpanded ? <ChevronUp className="w-5 h-5 mx-auto" /> : <ChevronDown className="w-5 h-5 mx-auto" />}
            </div>
        </div>
    );
}
