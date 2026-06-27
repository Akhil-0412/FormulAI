'use client';
import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { RaceResultBlock } from './RaceResultBlock';
import { RaceResult } from './data';

interface ProcessedRaceResult extends RaceResult {
    images: Record<number, string | null>;
    logos: Record<number, string | null>;
}

interface HistoricalSeason {
    year: number;
    results: ProcessedRaceResult[];
}

export default function HistoricalResultsToggle({
    historicalSeasons
}: {
    historicalSeasons: HistoricalSeason[]
}) {
    const [openSeasons, setOpenSeasons] = useState<Record<number, boolean>>({});

    const toggleSeason = (year: number) => {
        setOpenSeasons(prev => ({
            ...prev,
            [year]: !prev[year]
        }));
    };

    return (
        <div className="mt-10 pt-10 border-t border-white/10 flex flex-col gap-6">
            <div className="flex flex-col gap-2 mb-4">
                <h3 className="text-3xl font-black text-white italic tracking-tighter uppercase">Historical Results</h3>
                <p className="text-f1-muted text-lg">View podiums from previous seasons down to 2018.</p>
            </div>

            {historicalSeasons.map((season) => {
                const isOpen = !!openSeasons[season.year];

                return (
                    <div key={season.year} className="flex flex-col gap-0 glass-panel rounded-2xl border border-white/10 overflow-hidden">
                        <button
                            onClick={() => toggleSeason(season.year)}
                            className={`flex justify-between items-center w-full p-6 transition-all group ${isOpen ? 'bg-white/10 border-b border-white/10' : 'hover:bg-white/5'}`}
                        >
                            <div className="flex flex-col text-left">
                                <h3 className={`text-2xl font-bold transition-colors ${isOpen ? 'text-f1-papaya' : 'text-white group-hover:text-f1-papaya'}`}>
                                    {season.year} Season
                                </h3>
                                <p className="text-f1-muted text-sm">{season.results.length} Round{season.results.length !== 1 ? 's' : ''}</p>
                            </div>
                            {isOpen ? <ChevronUp className="w-8 h-8 text-f1-papaya" /> : <ChevronDown className="w-8 h-8 text-f1-muted group-hover:text-f1-papaya transition-colors" />}
                        </button>

                        {isOpen && (
                            <div className="p-8 flex flex-col gap-12 bg-black/20 animate-in slide-in-from-top-2 fade-in duration-300">
                                {season.results.map((result, idx) => (
                                    <RaceResultBlock
                                        key={`${season.year}-${idx}`}
                                        result={result}
                                        isHistorical={true}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
