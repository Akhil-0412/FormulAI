"use client";

import { LayoutGroup } from "framer-motion";
import TeamCard from "./TeamCard";
import { TEAM_LOGOS, TEAM_CARS, TEAM_COLORS } from "../constants/drivers";

/**
 * Team roster, keyed to the canonical names used everywhere else in the app
 * (TEAM_LOGOS / TEAM_CARS / driver.team) — "Red Bull" and "Racing Bulls",
 * not "Red Bull Racing" / "RB". The previous version used its own name
 * vocabulary and resolved photos by reading the team's asset folder and
 * taking files positionally (`drvFiles[0]`, `drvFiles[1]`) rather than by
 * driver identity. That's strictly worse than the fuzzy-name-matching bug
 * elsewhere — it doesn't even try to match the driver, just grabs whichever
 * two non-car, non-logo files happen to sort first. The Red Bull folder
 * contains a stray `2026cadillacserper01right.avif` (Pérez's Cadillac
 * photo, misplaced), so Hadjar's card was showing Pérez.
 *
 * Driver codes below resolve through the shared registry (`resolveDriver`
 * in TeamCard, via DriverAvatar), so a team's lineup is always the actual
 * driver, with the same verified crop as everywhere else.
 */
const TEAMS_DATA = [
    { name: "Red Bull", chassis: "RB20", drivers: ["VER", "HAD"], stats: { wins: 121, championships: 6, trackRecord: "Dominating era since 2021 with precise aerodynamic efficiency. Expect explosive pace on high-downforce tracks.", recentWins: ["2025 Abu Dhabi Grand Prix", "2025 Dutch Grand Prix"] } },
    { name: "Mercedes", chassis: "W17", drivers: ["RUS", "ANT"], stats: { wins: 125, championships: 8, trackRecord: "Historic consecutive constructor titles. Rebuilding aggressively with a focus on suspension geometry.", recentWins: ["2024 Belgian Grand Prix", "2024 British Grand Prix"] } },
    { name: "Ferrari", chassis: "SF-26", drivers: ["LEC", "HAM"], stats: { wins: 244, championships: 16, trackRecord: "The most historic team on the grid. Known for unmatched straight-line speed but prone to strategic gambles.", recentWins: ["2025 Italian Grand Prix", "2024 Monaco Grand Prix"] } },
    { name: "McLaren", chassis: "MCL40", drivers: ["NOR", "PIA"], stats: { wins: 184, championships: 8, trackRecord: "Resurgent force with phenomenal mid-season development curves. Highly adaptable to all track conditions.", recentWins: ["2025 Miami Grand Prix", "2024 Hungarian Grand Prix"] } },
    { name: "Aston Martin", chassis: "AMR26", drivers: ["ALO", "STR"], stats: { wins: 1, championships: 0, trackRecord: "Aggressive investment in facilities yielding high downforce monsters. Struggles on low-drag circuits.", recentWins: ["2020 Sakhir Grand Prix (as Racing Point)"] } },
    { name: "Alpine", chassis: "A526", drivers: ["GAS", "COL"], stats: { wins: 1, championships: 0, trackRecord: "The French works team. Extremely capable power unit but often hampered by internal turbulence.", recentWins: ["2021 Hungarian Grand Prix"] } },
    { name: "Williams", chassis: "FW48", drivers: ["ALB", "SAI"], stats: { wins: 114, championships: 9, trackRecord: "A sleeping giant slowly awakening. Cars historically boast extremely low drag, excelling at Monza and Baku.", recentWins: ["2012 Spanish Grand Prix"] } },
    { name: "Haas", chassis: "VF-25", drivers: ["OCO", "BEA"], stats: { wins: 0, championships: 0, trackRecord: "American underdog with deep Ferrari technical ties. Masters of the 'punch above their weight' one-lap pace.", recentWins: ["None (Best Finish: P4, Austria 2018)"] } },
    { name: "Racing Bulls", chassis: "VCARB 02", drivers: ["LAW", "LIN"], stats: { wins: 2, championships: 0, trackRecord: "Red Bull's aggressive sister team. Often acts as a proving ground for bold setup choices.", recentWins: ["2020 Italian Grand Prix (as AlphaTauri)"] } },
    { name: "Audi", chassis: "R26", drivers: ["HUL", "BOR"], stats: { wins: 0, championships: 0, trackRecord: "The highly anticipated German works team taking over Sauber. Massive resources poured into the aggressive 2026 regs.", recentWins: ["Debut Season in 2026"] } },
    { name: "Cadillac", chassis: "TBC", drivers: ["BOT", "PER"], stats: { wins: 0, championships: 0, trackRecord: "The brand new 11th team backed by GM. An absolute wildcard with a mix of veteran talent and raw potential.", recentWins: ["Debut Season in 2026"] } },
];

export default function TeamsPage() {
    const teams = TEAMS_DATA.map((team) => ({
        ...team,
        logoPath: TEAM_LOGOS[team.name] ?? null,
        carPath: TEAM_CARS[team.name] ?? null,
        color: TEAM_COLORS[team.name] ?? "var(--color-line-strong)",
    }));

    return (
        <div className="max-w-[1500px] mx-auto pb-10">
            <div className="mb-6">
                <h1 className="h-display text-fg mb-2">Constructors</h1>
                <p className="label-xs">2026 grid — team statistics and lineups</p>
            </div>

            {/* LayoutGroup batches every card's layout animation into one
                synchronized measurement/animation pass. Without it, each
                motion.div's `layout` prop still works individually, but 11
                siblings all changing position in the same commit isn't
                guaranteed to resolve as one coordinated motion — which is
                what read as "neighbours snap, then only the clicked card
                animates". Grouping them fixes that. */}
            <LayoutGroup>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 auto-rows-min">
                    {teams.map((team) => (
                        <TeamCard key={team.name} team={team} />
                    ))}
                </div>
            </LayoutGroup>
        </div>
    );
}
