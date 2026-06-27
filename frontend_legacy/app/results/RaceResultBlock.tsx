import Image from 'next/image';
import { Calendar, MapPin, AlignLeft } from "lucide-react";
import { TEAM_THEMES } from '../constants/themes';
import { RaceResult } from './data';

const PODIUM_COLORS = {
    1: { name: "Gold", hex: "#FFD700", glow: "group-hover:shadow-[0_0_30px_rgba(255,215,0,0.6)]", border: "border-t-[#FFD700]", dropShadow: "group-hover:drop-shadow-[0_0_20px_rgba(255,215,0,0.8)]" },
    2: { name: "Silver", hex: "#C0C0C0", glow: "group-hover:shadow-[0_0_30px_rgba(192,192,192,0.6)]", border: "border-t-[#C0C0C0]", dropShadow: "group-hover:drop-shadow-[0_0_20px_rgba(192,192,192,0.8)]" },
    3: { name: "Bronze", hex: "#CD7F32", glow: "group-hover:shadow-[0_0_30px_rgba(205,127,50,0.6)]", border: "border-t-[#CD7F32]", dropShadow: "group-hover:drop-shadow-[0_0_20px_rgba(205,127,50,0.8)]" },
};

export interface ProcessedRaceResult extends RaceResult {
    images?: Record<number, string | null>;
    logos?: Record<number, string | null>;
}

export const RaceResultBlock = ({
    result,
    isHistorical = false,
}: {
    result: ProcessedRaceResult,
    isHistorical?: boolean,
}) => (
    <div className="flex flex-col gap-6">
        <div className="flex flex-col md:flex-row md:items-end justify-between px-4 pb-2 border-b border-white/10">
            <div>
                <h2 className={`font-black text-white italic tracking-tighter uppercase ${isHistorical ? 'text-2xl opacity-90' : 'text-3xl'}`}>{result.race}</h2>
                <div className="flex items-center gap-4 text-f1-muted mt-1">
                    <span className="flex items-center gap-1"><Calendar className="w-4 h-4" /> {result.date}</span>
                    <span className="flex items-center gap-1"><MapPin className="w-4 h-4" /> {result.location}</span>
                </div>
            </div>

            <button className="flex items-center gap-2 px-4 py-2 mt-4 md:mt-0 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 hover:text-white transition-colors text-f1-muted font-bold text-sm tracking-widest uppercase group-button">
                <AlignLeft className="w-4 h-4" /> View Full Classification
            </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {result.podium.map((p) => {
                const theme = TEAM_THEMES[p.team] || { primary: "#FFFFFF" };
                const podiumClass = PODIUM_COLORS[p.pos as keyof typeof PODIUM_COLORS];
                const imgPath = result.images?.[p.pos] || null;
                const logoPath = result.logos?.[p.pos] || null;

                return (
                    <div
                        key={p.pos}
                        className={`glass-panel overflow-hidden flex flex-col items-center group transition-all duration-500 hover:translate-y-[-8px] border-t-4 ${podiumClass.border}`}
                    >
                        <div className="relative w-full h-[320px] bg-gradient-to-t from-f1-navy via-transparent to-transparent overflow-hidden">
                            <div className="absolute top-4 left-6 text-7xl font-black text-white/5 italic pointer-events-none transition-colors duration-500" style={{ color: `color-mix(in srgb, ${podiumClass.hex} 10%, transparent)` }}>
                                P{p.pos}
                            </div>

                            <div className="absolute inset-0 flex items-end justify-center">
                                {imgPath ? (
                                    <div className="relative w-full h-full transform transition-transform duration-700 group-hover:scale-110">
                                        <div className={`absolute inset-0 transition-opacity duration-500 opacity-0 group-hover:opacity-100 mix-blend-screen pointer-events-none`} />
                                        <Image
                                            src={imgPath}
                                            alt={p.driver}
                                            fill
                                            className={`object-cover object-top filter grayscale-[0.2] transition-all duration-500 group-hover:grayscale-0 ${podiumClass.dropShadow}`}
                                            unoptimized
                                        />
                                    </div>
                                ) : (
                                    <div className="w-full h-full flex items-center justify-center text-white/10 text-6xl">👤</div>
                                )}
                            </div>

                            <div className={`absolute top-6 right-6 w-10 h-10 rounded-lg flex items-center justify-center font-black shadow-xl text-f1-navy transition-colors`} style={{ backgroundColor: podiumClass.hex }}>
                                {p.pos}
                            </div>
                        </div>

                        <div className="w-full p-6 text-center bg-white/5 border-t border-white/5 relative z-10 backdrop-blur-xl">
                            <h3 className="text-2xl font-black text-white italic tracking-tight uppercase group-hover:scale-105 transition-transform" style={{ textShadow: `0 0 10px ${podiumClass.hex}80` }}>{p.driver}</h3>
                            <div className="flex items-center justify-center gap-3 mt-2">
                                {logoPath ? (
                                    <div className="relative w-6 h-6">
                                        <Image src={logoPath} alt={p.team} fill className="object-contain" unoptimized />
                                    </div>
                                ) : (
                                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: theme.primary }} />
                                )}
                                <p className="text-xs font-bold text-f1-muted tracking-widest uppercase">{p.team}</p>
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    </div>
);
