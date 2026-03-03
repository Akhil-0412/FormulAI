import fs from 'fs';
import path from 'path';
import { Trophy } from "lucide-react";
import { RECENT_RESULTS, HISTORICAL_SEASONS, RaceResult } from './data';
import { RaceResultBlock } from './RaceResultBlock';
import HistoricalResultsToggle from './HistoricalResultsToggle';

const FOLDER_MAP: Record<string, string> = {
    "Red Bull Racing": "Red Bull Racing",
    "Mercedes": "Mercedes",
    "Ferrari": "Ferrari",
    "McLaren": "McLaren",
    "Aston Martin": "Aston Martin",
    "Alpine": "Alpine",
    "Williams": "Williams",
    "Haas": "Haas F1 Team",
    "RB": "Racing Bulls",
    "Audi": "Audi",
    "Cadillac": "Cadillac",
    "Alfa Romeo R.": "Alfa Romeo", // Historical teams mappings
    "AlphaTauri": "AlphaTauri",
    "Renault": "Renault",
    "Racing Point": "Racing Point"
};

// --- HELPER LOGIC (Server-Side) ---
export const getDriverImage = (driverName: string, team: string) => {
    let folderName = FOLDER_MAP[team];
    // Specific overrides for 2026 season (as per original comment, though now applied to historical for demo)
    if (driverName === "Carlos Sainz" && team === "Ferrari") folderName = "Williams";
    if (driverName === "Lewis Hamilton" && team === "Mercedes") folderName = "Ferrari";

    if (!folderName) return null;
    try {
        const publicDir = path.join(process.cwd(), 'public');
        const teamDir = path.join(publicDir, 'assets', 'Teams', folderName);
        if (fs.existsSync(teamDir)) {
            const files = fs.readdirSync(teamDir);
            const nameParts = driverName.toLowerCase().split(' ');

            const first3 = nameParts[0].substring(0, 3);
            const last3 = nameParts[nameParts.length - 1].substring(0, 3);
            const combined = first3 + last3;

            const match = files.find(f => {
                const fname = f.toLowerCase();
                if (fname.includes('logo')) return false;
                if (fname.includes('car') && !fname.includes('carsai')) return false; // Exclude car images unless specific

                return fname.includes(combined) ||
                    fname.includes(nameParts[nameParts.length - 1]) ||
                    fname.includes(nameParts[0]);
            });
            if (match) return `/assets/Teams/${folderName}/${match}`;
        }
    } catch (e) { console.error(`Error reading driver image for ${driverName} (${team}):`, e) }
    return null;
};

export const getTeamLogo = (team: string) => {
    const folderName = FOLDER_MAP[team];
    if (!folderName) return null;
    try {
        const publicDir = path.join(process.cwd(), 'public');
        const teamDir = path.join(publicDir, 'assets', 'Teams', folderName);
        if (fs.existsSync(teamDir)) {
            const files = fs.readdirSync(teamDir);
            const match = files.find(f => f.toLowerCase().includes('logo'));
            if (match) return `/assets/Teams/${folderName}/${match}`;
        }
    } catch (e) { console.error(`Error reading team logo for ${team}:`, e) }
    return null;
};

// MAIN PAGE (Server Component)
export default function ResultsPage() {
    return (
        <div className="flex flex-col gap-10 max-w-7xl mx-auto mb-20 animate-in fade-in duration-700">
            <div className="flex flex-col gap-2">
                <h1 className="text-4xl md:text-5xl font-black tracking-tight text-white italic tracking-tighter" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>
                    Race Results
                </h1>
                <p className="text-f1-muted text-lg italic tracking-wider font-semibold" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>Podium finishes and full classifications covering the 2026 season back to 2018.</p>
            </div>

            {/* 2026 Recent Results */}
            <div className="flex flex-col gap-12">
                {RECENT_RESULTS.length > 0 ? (
                    RECENT_RESULTS.map((result, idx) => {
                        const images: Record<number, string | null> = {};
                        const logos: Record<number, string | null> = {};

                        result.podium.forEach(p => {
                            images[p.pos] = getDriverImage(p.driver, p.team);
                            logos[p.pos] = getTeamLogo(p.team);
                        });

                        const processedResult = { ...result, images, logos };

                        return (
                            <RaceResultBlock
                                key={idx}
                                result={processedResult}
                            />
                        );
                    })
                ) : (
                    <div className="p-12 text-center rounded-3xl glass-panel border border-dashed border-white/20">
                        <p className="text-2xl font-bold text-white/50">No results yet for the 2026 Season.</p>
                        <p className="text-f1-muted mt-2">Check back after the first race in Bahrain!</p>
                    </div>
                )}
            </div>

            {/* Historical Matches wrapped in a Client Component */}
            {/* We pass the data and the server-side resolving functions as props */}
            <HistoricalResultsToggle
                historicalSeasons={HISTORICAL_SEASONS.map(season => ({
                    ...season,
                    results: season.results.map(result => {
                        const images: Record<number, string | null> = {};
                        const logos: Record<number, string | null> = {};

                        result.podium.forEach(p => {
                            images[p.pos] = getDriverImage(p.driver, p.team);
                            logos[p.pos] = getTeamLogo(p.team);
                        });

                        return {
                            ...result,
                            images,
                            logos
                        };
                    })
                }))}
            />
        </div>
    );
}
