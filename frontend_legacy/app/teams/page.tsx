import fs from 'fs';
import path from 'path';
import Image from 'next/image';
import TeamCard from './TeamCard';

const TEAMS_DATA = [
    { name: "Red Bull Racing", chassis: "RB20", border: "border-t-[#0600EF]", drivers: ["VER", "HAD"], stats: { wins: 121, championships: 6, trackRecord: "Dominating era since 2021 with precise aerodynamic efficiency. Expect explosive pace on high-downforce tracks.", recentWins: ["2025 Abu Dhabi Grand Prix", "2025 Dutch Grand Prix"] } },
    { name: "Mercedes", chassis: "W17", border: "border-t-f1-teal", drivers: ["RUS", "ANT"], stats: { wins: 125, championships: 8, trackRecord: "Historic consecutive constructor titles. Rebuilding aggressively with a focus on suspension geometry.", recentWins: ["2024 Belgian Grand Prix", "2024 British Grand Prix"] } },
    { name: "Ferrari", chassis: "SF-26", border: "border-t-f1-red", drivers: ["LEC", "HAM"], stats: { wins: 244, championships: 16, trackRecord: "The most historic team on the grid. Known for unmatched straight-line speed but prone to strategic gambles.", recentWins: ["2025 Italian Grand Prix", "2024 Monaco Grand Prix"] } },
    { name: "McLaren", chassis: "MCL40", border: "border-t-f1-papaya", drivers: ["NOR", "PIA"], stats: { wins: 184, championships: 8, trackRecord: "Resurgent force with phenomenal mid-season development curves. Highly adaptable to all track conditions.", recentWins: ["2025 Miami Grand Prix", "2024 Hungarian Grand Prix"] } },
    { name: "Aston Martin", chassis: "AMR26", border: "border-t-f1-green", drivers: ["ALO", "STR"], stats: { wins: 1, championships: 0, trackRecord: "Aggressive investment in facilities yielding high downforce monsters. Struggles on low-drag circuits.", recentWins: ["2020 Sakhir Grand Prix (as Racing Point)"] } },
    { name: "Alpine", chassis: "A526", border: "border-t-white", drivers: ["GAS", "COL"], stats: { wins: 1, championships: 0, trackRecord: "The French works team. Extremely capable power unit but often hampered by internal turbulence.", recentWins: ["2021 Hungarian Grand Prix"] } },
    { name: "Williams", chassis: "FW48", border: "border-t-white", drivers: ["ALB", "SAI"], stats: { wins: 114, championships: 9, trackRecord: "A sleeping giant slowly awakening. Cars historically boast extremely low drag, excelling at Monza and Baku.", recentWins: ["2012 Spanish Grand Prix"] } },
    { name: "Haas", chassis: "VF-25", border: "border-t-white", drivers: ["OCO", "BEA"], stats: { wins: 0, championships: 0, trackRecord: "American underdog with deep Ferrari technical ties. Masters of the 'punch above their weight' one-lap pace.", recentWins: ["None (Best Finish: P4, Austria 2018)"] } },
    { name: "RB", chassis: "VCARB 02", border: "border-t-white", drivers: ["LAW", "LIN"], stats: { wins: 2, championships: 0, trackRecord: "Red Bull's aggressive sister team. Often acts as a proving ground for bold setup choices.", recentWins: ["2020 Italian Grand Prix (as AlphaTauri)"] } },
    { name: "Audi", chassis: "R26", border: "border-t-white", drivers: ["HUL", "BOR"], stats: { wins: 0, championships: 0, trackRecord: "The highly anticipated German works team taking over Sauber. Massive resources poured into the aggressive 2026 regs.", recentWins: ["Debut Season in 2026"] } },
    { name: "Cadillac", chassis: "TBC", border: "border-t-[#C0C0C0]", drivers: ["BOT", "PER"], stats: { wins: 0, championships: 0, trackRecord: "The brand new 11th team backed by GM. An absolute wildcard with a mix of veteran talent and raw potential.", recentWins: ["Debut Season in 2026"] } },
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

export default function TeamsPage() {
    const publicDir = path.join(process.cwd(), 'public');
    const teamsAssetDir = path.join(publicDir, 'assets', 'Teams');

    const processedTeams = TEAMS_DATA.map(team => {
        const folderName = FOLDER_MAP[team.name];
        const teamSpecificDir = path.join(teamsAssetDir, folderName);

        let carPath = null;
        let logoPath = null;
        let drv1Path = null;
        let drv2Path = null;

        if (fs.existsSync(teamSpecificDir)) {
            const files = fs.readdirSync(teamSpecificDir);

            const carFiles = files.filter(f => f.toLowerCase().includes('car'));
            const logoFiles = files.filter(f => f.toLowerCase().includes('logo'));
            const drvFiles = files.filter(f => !f.toLowerCase().includes('car') && !f.toLowerCase().includes('logo'));

            if (carFiles.length > 0) carPath = `/assets/Teams/${folderName}/${carFiles[0]}`;
            if (logoFiles.length > 0) logoPath = `/assets/Teams/${folderName}/${logoFiles[0]}`;

            if (drvFiles.length >= 2) {
                drv1Path = `/assets/Teams/${folderName}/${drvFiles[0]}`;
                drv2Path = `/assets/Teams/${folderName}/${drvFiles[1]}`;
            } else if (drvFiles.length === 1) {
                drv1Path = `/assets/Teams/${folderName}/${drvFiles[0]}`;
            }
        }

        return { ...team, carPath, logoPath, drv1Path, drv2Path };
    });

    return (
        <div className="flex flex-col gap-8 max-w-7xl mx-auto mb-20 animate-in fade-in duration-700">
            <div className="flex flex-col gap-2">
                <h1 className="text-4xl md:text-5xl font-black tracking-tight text-white italic tracking-tighter" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>
                    Constructor Teams
                </h1>
                <p className="text-f1-muted text-lg italic tracking-wider font-semibold" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>Explore the 2026 Grid with in-depth team statistics.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 auto-rows-min">
                {processedTeams.map((team) => (
                    <TeamCard key={team.name} team={team} />
                ))}
            </div>
        </div>
    );
}
