import fs from 'fs';
import path from 'path';
import Image from 'next/image';
import { Trophy, Medal, Flag } from "lucide-react";

const DRIVER_STANDINGS = [
    { pos: 1, driver: "Max Verstappen", team: "Red Bull Racing", points: 412 },
    { pos: 2, driver: "Charles Leclerc", team: "Ferrari", points: 368 },
    { pos: 3, driver: "Lando Norris", team: "McLaren", points: 315 },
    { pos: 4, driver: "George Russell", team: "Mercedes", points: 280 },
    { pos: 5, driver: "Lewis Hamilton", team: "Ferrari", points: 245 },
];

const TEAM_STANDINGS = [
    { pos: 1, team: "Ferrari", points: 613, color: "border-l-f1-red" },
    { pos: 2, team: "Red Bull Racing", points: 580, color: "border-l-[#0600EF]" },
    { pos: 3, team: "McLaren", points: 495, color: "border-l-f1-papaya" },
    { pos: 4, team: "Mercedes", points: 410, color: "border-l-f1-teal" },
];

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
    "Cadillac": "Cadillac"
};

export default function StandingsPage() {
    const publicDir = path.join(process.cwd(), 'public');
    const teamsAssetDir = path.join(publicDir, 'assets', 'Teams');

    const processedDrivers = DRIVER_STANDINGS.map(d => {
        const folderName = FOLDER_MAP[d.team];
        const teamSpecificDir = path.join(teamsAssetDir, folderName);
        let driverPath = null;

        if (fs.existsSync(teamSpecificDir)) {
            const files = fs.readdirSync(teamSpecificDir);

            // Refined matching:
            // 1. Try first 3 letters of first name + first 3 letters of last name (filesystem pattern)
            // 2. Try just the last name
            // 3. Try any part of the name
            const nameParts = d.driver.toLowerCase().split(' ');
            const first3 = nameParts[0].substring(0, 3);
            const last3 = nameParts[nameParts.length - 1].substring(0, 3);
            const combined = first3 + last3;

            const match = files.find(f => {
                const fname = f.toLowerCase();
                if (fname.includes('car') || fname.includes('logo')) return false;
                return fname.includes(combined) ||
                    fname.includes(nameParts[nameParts.length - 1]) ||
                    fname.includes(nameParts[0]);
            });

            if (match) driverPath = `/assets/Teams/${folderName}/${match}`;
        }
        return { ...d, imagePath: driverPath };
    });

    const processedTeams = TEAM_STANDINGS.map(t => {
        const folderName = FOLDER_MAP[t.team];
        const teamSpecificDir = path.join(teamsAssetDir, folderName);
        let logoPath = null;

        if (fs.existsSync(teamSpecificDir)) {
            const files = fs.readdirSync(teamSpecificDir);
            const match = files.find(f => f.toLowerCase().includes('logo'));
            if (match) logoPath = `/assets/Teams/${folderName}/${match}`;
        }
        return { ...t, logoPath };
    });

    return (
        <div className="flex flex-col gap-10 max-w-7xl mx-auto mb-20 animate-in fade-in duration-700">
            <div className="flex flex-col gap-2">
                <h1 className="text-4xl md:text-5xl font-black tracking-tight text-white italic tracking-tighter" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>
                    Championship Standings
                </h1>
                <p className="text-f1-muted text-lg italic tracking-wider font-semibold" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>Current 2026 Season layout.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

                {/* Drivers */}
                <div className="glass-panel rounded-2xl p-6 overflow-hidden relative">
                    <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
                        <Medal className="w-6 h-6 text-f1-red" /> Drivers
                    </h2>
                    <div className="flex flex-col gap-3">
                        {processedDrivers.map((d, i) => (
                            <div key={d.driver} className="flex items-center justify-between p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-all duration-300 group">
                                <div className="flex items-center gap-4">
                                    <span className={`text-xl font-bold w-6 text-center ${i === 0 ? "text-f1-papaya" : "text-f1-muted"}`}>{d.pos}</span>

                                    {/* Driver Face */}
                                    <div className="relative w-12 h-12 rounded-full overflow-hidden border-2 border-white/10 group-hover:border-f1-red transition-colors bg-f1-navy">
                                        {d.imagePath ? (
                                            <Image src={d.imagePath} alt={d.driver} fill className="object-cover object-top" unoptimized />
                                        ) : (
                                            <div className="w-full h-full flex items-center justify-center text-xs text-white/20">👤</div>
                                        )}
                                    </div>

                                    <div>
                                        <h4 className="text-white font-semibold text-lg">{d.driver}</h4>
                                        <p className="text-sm text-f1-muted">{d.team}</p>
                                    </div>
                                </div>
                                <div className="text-2xl font-black w-16 text-right text-white tabular-nums">{d.points}</div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Constructors */}
                <div className="glass-panel rounded-2xl p-6 overflow-hidden relative">
                    <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
                        <Flag className="w-6 h-6 text-f1-teal" /> Constructors
                    </h2>
                    <div className="flex flex-col gap-3">
                        {processedTeams.map((t, i) => (
                            <div key={t.team} className={`flex items-center justify-between p-4 rounded-xl bg-white/5 border border-white/10 border-l-4 ${t.color} hover:bg-white/10 transition-all duration-300 group`}>
                                <div className="flex items-center gap-4">
                                    <span className={`text-xl font-bold w-6 text-center ${i === 0 ? "text-f1-papaya" : "text-f1-muted"}`}>{t.pos}</span>
                                    <h4 className="text-white font-semibold text-lg">{t.team}</h4>
                                </div>

                                <div className="flex items-center gap-6">
                                    {/* Team Logo at the end of the bar */}
                                    {t.logoPath && (
                                        <div className="relative w-8 h-8 opacity-40 group-hover:opacity-100 transition-opacity">
                                            <Image src={t.logoPath} alt={t.team} fill className="object-contain" unoptimized />
                                        </div>
                                    )}
                                    <div className="text-2xl font-black w-16 text-right text-white tabular-nums">{t.points}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

            </div>
        </div>
    );
}
