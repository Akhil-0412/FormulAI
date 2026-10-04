/**
 * Season results loader.
 *
 * Jolpica caps `limit` at 100 server-side and reports the real row count in
 * `total`, so a season of results (rounds × ~22 drivers) never arrives in a
 * single response. Asking for limit=1000 and trusting it is exactly the bug
 * that left the backend training on the first five races of every season —
 * so page through `offset` here too.
 */

const BASE = "https://api.jolpi.ca/ergast/f1";
const PAGE = 100;

export type RoundResult = {
    round: number;
    raceName: string;
    circuitName?: string;
    date: string;
    /** driverId → finishing position (null when they didn't finish) */
    finishers: Record<string, number | null>;
    points: Record<string, number>;
    /** driverId → Jolpica constructorId, for the round they actually raced
     *  for (a driver can switch teams mid-season, so this is captured per
     *  round rather than assumed static). */
    constructorOf: Record<string, string>;
};

type RaceJson = {
    round: string;
    raceName: string;
    date: string;
    Circuit?: { circuitName?: string };
    Results?: Array<{
        position?: string;
        positionText?: string;
        points?: string;
        Driver?: { driverId?: string };
        Constructor?: { constructorId?: string; name?: string };
    }>;
};

/**
 * Jolpica constructorId → the display name used throughout this app
 * (TEAM_LOGOS / TEAM_CARS keys, driver.team values). Verified against a
 * live 2026 results response rather than guessed — "rb" in particular
 * doesn't spell out to "Racing Bulls" and would silently fail to match a
 * logo if assumed.
 */
export const CONSTRUCTOR_NAME: Record<string, string> = {
    mercedes: "Mercedes",
    ferrari: "Ferrari",
    mclaren: "McLaren",
    red_bull: "Red Bull",
    haas: "Haas",
    rb: "Racing Bulls",
    audi: "Audi",
    alpine: "Alpine",
    williams: "Williams",
    cadillac: "Cadillac",
    aston_martin: "Aston Martin",
};

export async function fetchSeasonResults(year: number): Promise<RoundResult[]> {
    const merged = new Map<string, RaceJson>();
    let offset = 0;

    for (let guard = 0; guard < 30; guard++) {
        const res = await fetch(
            `${BASE}/${year}/results.json?limit=${PAGE}&offset=${offset}`
        );
        if (!res.ok) break;
        const json = await res.json();
        const mr = json?.MRData;
        const races: RaceJson[] = mr?.RaceTable?.Races ?? [];

        for (const r of races) {
            const existing = merged.get(r.round);
            if (!existing) {
                merged.set(r.round, { ...r, Results: [...(r.Results ?? [])] });
            } else {
                // A race's rows can straddle a page boundary.
                existing.Results = [...(existing.Results ?? []), ...(r.Results ?? [])];
            }
        }

        const total = Number(mr?.total ?? 0);
        offset += PAGE;
        if (!races.length || offset >= total) break;
    }

    return [...merged.values()]
        .map((r) => {
            const finishers: Record<string, number | null> = {};
            const points: Record<string, number> = {};
            const constructorOf: Record<string, string> = {};
            for (const row of r.Results ?? []) {
                const id = row.Driver?.driverId;
                if (!id) continue;
                const posNum = Number(row.position);
                // positionText is "R"/"W"/"D" for retirements etc.
                finishers[id] = Number.isFinite(posNum) && posNum > 0 ? posNum : null;
                points[id] = Number(row.points ?? 0);
                if (row.Constructor?.constructorId) {
                    constructorOf[id] = row.Constructor.constructorId;
                }
            }
            return {
                round: Number(r.round),
                raceName: r.raceName,
                circuitName: r.Circuit?.circuitName,
                date: r.date,
                finishers,
                points,
                constructorOf,
            };
        })
        .sort((a, b) => a.round - b.round);
}

/**
 * Short x-axis labels.
 *
 * Truncating the race name collides — "Australian" and "Austrian" both give
 * AUS, silently mislabelling two different races — so use the conventional
 * three-letter codes. Anything unmapped falls back to truncation, extended
 * until it's unique against the rest of the calendar.
 */
const RACE_CODES: Record<string, string> = {
    australian: "AUS", austrian: "AUT", bahrain: "BHR", chinese: "CHN",
    japanese: "JPN", miami: "MIA", canadian: "CAN", monaco: "MON",
    spanish: "ESP", british: "GBR", belgian: "BEL", hungarian: "HUN",
    dutch: "NED", italian: "ITA", singapore: "SGP", azerbaijan: "AZE",
    mexican: "MEX", "mexico city": "MEX", brazilian: "BRA",
    "são paulo": "BRA", "sao paulo": "BRA", qatar: "QAT",
    "abu dhabi": "ABU", "saudi arabian": "SAU", "emilia romagna": "IMO",
    "united states": "USA", "las vegas": "LVG", french: "FRA",
    portuguese: "POR", russian: "RUS", turkish: "TUR", styrian: "STY",
    "70th anniversary": "ANN", eifel: "EIF", tuscan: "TUS", sakhir: "SAK",
    madrid: "MAD",
};

export function buildRoundLabels(rounds: RoundResult[]): string[] {
    const names = rounds.map((r) =>
        r.raceName.replace(/ Grand Prix$/i, "").trim().toLowerCase()
    );

    return names.map((name, i) => {
        const mapped = RACE_CODES[name];
        if (mapped) return mapped;

        // Unmapped: truncate, lengthening until unique.
        const clean = name.replace(/[^a-z]/g, "");
        for (let len = 3; len <= clean.length; len++) {
            const candidate = clean.slice(0, len).toUpperCase();
            const clashes = names.some((other, j) => {
                if (j === i) return false;
                const otherCode =
                    RACE_CODES[other] ?? other.replace(/[^a-z]/g, "").slice(0, len).toUpperCase();
                return otherCode === candidate;
            });
            if (!clashes) return candidate;
        }
        return clean.slice(0, 3).toUpperCase();
    });
}

/** Cumulative championship standings derived from the same results. */
export function computeStandings(rounds: RoundResult[]) {
    const totals = new Map<string, number>();
    for (const r of rounds) {
        for (const [driverId, pts] of Object.entries(r.points)) {
            totals.set(driverId, (totals.get(driverId) ?? 0) + (pts || 0));
        }
    }
    return [...totals.entries()]
        .map(([driverId, points]) => ({ driverId, points }))
        .sort((a, b) => b.points - a.points);
}

/** Cumulative constructor standings, summed from the same per-driver results
 *  used for the driver table — so the two can't disagree with each other. */
export function computeConstructorStandings(rounds: RoundResult[]) {
    const totals = new Map<string, number>();
    for (const r of rounds) {
        for (const [driverId, pts] of Object.entries(r.points)) {
            const constructorId = r.constructorOf[driverId];
            if (!constructorId) continue;
            totals.set(constructorId, (totals.get(constructorId) ?? 0) + (pts || 0));
        }
    }
    return [...totals.entries()]
        .map(([constructorId, points]) => ({
            constructorId,
            name: CONSTRUCTOR_NAME[constructorId] ?? constructorId,
            points,
        }))
        .sort((a, b) => b.points - a.points);
}

/** Pivot rounds → one series per driver, with cumulative points. */
export function toDriverSeries(rounds: RoundResult[]) {
    const ids = new Set<string>();
    for (const r of rounds) Object.keys(r.finishers).forEach((d) => ids.add(d));

    return [...ids].map((driverId) => ({
        driverId,
        positions: rounds.map((r) =>
            driverId in r.finishers ? r.finishers[driverId] : null
        ),
        points: rounds.reduce((sum, r) => sum + (r.points[driverId] ?? 0), 0),
    }));
}
