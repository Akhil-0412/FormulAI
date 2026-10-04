/**
 * 2026 grid registry — driver id → portrait, team, colour.
 *
 * Keys are Ergast-style ids, which is what the backend returns
 * (`max_verstappen`, `arvid_lindblad`, …). `resolveDriver` also accepts
 * surnames and loose casing so a payload that says "Norris" still matches.
 *
 * All portraits, including the 2026 arrivals (Hadjar, Lindblad, Hülkenberg,
 * Bortoleto, Bottas, Pérez, Sainz), are the same 440×1375 full-body cutout
 * format — confirmed by scanning pixel content in each file, not assumed —
 * so DriverAvatar applies one crop to every entry here.
 */

export type Driver = {
    id: string;
    code: string;
    name: string;
    team: string;
    color: string;
    img: string;
    nationality: string;
};

const T = {
    mercedes: "#00D2BE",
    ferrari: "#E80020",
    redbull: "#3671C6",
    mclaren: "#FF8000",
    astonmartin: "#229971",
    alpine: "#0093CC",
    williams: "#64C4FF",
    racingbulls: "#6692FF",
    haas: "#B6BABD",
    audi: "#00E701",
    cadillac: "#B59A6A",
} as const;

const A = "/assets/Teams";

export const DRIVERS: Driver[] = [
    // Mercedes
    { id: "antonelli", code: "ANT", name: "Kimi Antonelli", team: "Mercedes", color: T.mercedes, img: `https://media.formula1.com/image/upload/c_lfill,w_440/q_auto/d_common:f1:2026:fallback:driver:2026fallbackdriverright.webp/v1740000001/common/f1/2026/mercedes/andant01/2026mercedesandant01right.webp`, nationality: "Italian" },
    { id: "russell", code: "RUS", name: "George Russell", team: "Mercedes", color: T.mercedes, img: `${A}/Mercedes/2025mercedesgeorus01right.avif`, nationality: "British" },

    // Ferrari
    { id: "leclerc", code: "LEC", name: "Charles Leclerc", team: "Ferrari", color: T.ferrari, img: `${A}/Ferrari/2025ferrarichalec01right.avif`, nationality: "Monégasque" },
    { id: "hamilton", code: "HAM", name: "Lewis Hamilton", team: "Ferrari", color: T.ferrari, img: `${A}/Ferrari/2025ferrarilewham01right.avif`, nationality: "British" },

    // Red Bull
    { id: "max_verstappen", code: "VER", name: "Max Verstappen", team: "Red Bull", color: T.redbull, img: `${A}/Red Bull Racing/2025redbullracingmaxver01right.avif`, nationality: "Dutch" },
    { id: "hadjar", code: "HAD", name: "Isack Hadjar", team: "Red Bull", color: T.redbull, img: `https://media.formula1.com/image/upload/c_lfill,w_440/q_auto/d_common:f1:2026:fallback:driver:2026fallbackdriverright.webp/v1740000001/common/f1/2026/redbullracing/isahad01/2026redbullracingisahad01right.webp`, nationality: "French" },

    // McLaren
    { id: "norris", code: "NOR", name: "Lando Norris", team: "McLaren", color: T.mclaren, img: `${A}/McLaren/2025mclarenlannor01right.avif`, nationality: "British" },
    { id: "piastri", code: "PIA", name: "Oscar Piastri", team: "McLaren", color: T.mclaren, img: `${A}/McLaren/2025mclarenoscpia01right.avif`, nationality: "Australian" },

    // Aston Martin
    { id: "alonso", code: "ALO", name: "Fernando Alonso", team: "Aston Martin", color: T.astonmartin, img: `${A}/Aston Martin/astonmartinferalo.avif`, nationality: "Spanish" },
    { id: "stroll", code: "STR", name: "Lance Stroll", team: "Aston Martin", color: T.astonmartin, img: `${A}/Aston Martin/astonmartinlanstr.avif`, nationality: "Canadian" },

    // Alpine
    { id: "gasly", code: "GAS", name: "Pierre Gasly", team: "Alpine", color: T.alpine, img: `${A}/Alpine/alpinepiegas.avif`, nationality: "French" },
    { id: "colapinto", code: "COL", name: "Franco Colapinto", team: "Alpine", color: T.alpine, img: `${A}/Alpine/alpinefracol.avif`, nationality: "Argentine" },

    // Haas
    { id: "ocon", code: "OCO", name: "Esteban Ocon", team: "Haas", color: T.haas, img: `${A}/Haas F1 Team/2025haasestoco01right.avif`, nationality: "French" },
    { id: "bearman", code: "BEA", name: "Oliver Bearman", team: "Haas", color: T.haas, img: `${A}/Haas F1 Team/2025haasolibea01right.avif`, nationality: "British" },

    // Williams
    { id: "albon", code: "ALB", name: "Alexander Albon", team: "Williams", color: T.williams, img: `${A}/Williams/williamsalealb.avif`, nationality: "Thai" },
    { id: "sainz", code: "SAI", name: "Carlos Sainz", team: "Williams", color: T.williams, img: `${A}/Williams/williamscarsai.avif`, nationality: "Spanish" },

    // Racing Bulls
    { id: "lawson", code: "LAW", name: "Liam Lawson", team: "Racing Bulls", color: T.racingbulls, img: `${A}/Racing Bulls/2025racingbullslialaw01right.avif`, nationality: "New Zealander" },
    { id: "arvid_lindblad", code: "LIN", name: "Arvid Lindblad", team: "Racing Bulls", color: T.racingbulls, img: `https://media.formula1.com/image/upload/c_lfill,w_440/q_auto/d_common:f1:2026:fallback:driver:2026fallbackdriverright.webp/v1740000001/common/f1/2026/racingbulls/arvlin01/2026racingbullsarvlin01right.webp`, nationality: "British" },

    // Audi
    { id: "hulkenberg", code: "HUL", name: "Nico Hülkenberg", team: "Audi", color: T.audi, img: `https://media.formula1.com/image/upload/c_lfill,w_440/q_auto/d_common:f1:2026:fallback:driver:2026fallbackdriverright.webp/v1740000001/common/f1/2026/audi/nichul01/2026audinichul01right.webp`, nationality: "German" },
    { id: "bortoleto", code: "BOR", name: "Gabriel Bortoleto", team: "Audi", color: T.audi, img: `https://media.formula1.com/image/upload/c_lfill,w_440/q_auto/d_common:f1:2026:fallback:driver:2026fallbackdriverright.webp/v1740000001/common/f1/2026/audi/gabbor01/2026audigabbor01right.webp`, nationality: "Brazilian" },

    // Cadillac
    { id: "perez", code: "PER", name: "Sergio Pérez", team: "Cadillac", color: T.cadillac, img: `https://media.formula1.com/image/upload/c_lfill,w_440/q_auto/d_common:f1:2026:fallback:driver:2026fallbackdriverright.webp/v1740000001/common/f1/2026/cadillac/serper01/2026cadillacserper01right.webp`, nationality: "Mexican" },
    { id: "bottas", code: "BOT", name: "Valtteri Bottas", team: "Cadillac", color: T.cadillac, img: `https://media.formula1.com/image/upload/c_lfill,w_440/q_auto/d_common:f1:2026:fallback:driver:2026fallbackdriverright.webp/v1740000001/common/f1/2026/cadillac/valbot01/2026cadillacvalbot01right.webp`, nationality: "Finnish" },
];

export const TEAM_LOGOS: Record<string, string> = {
    Mercedes: `${A}/Mercedes/2025mercedeslogowhite.avif`,
    Ferrari: `${A}/Ferrari/2025ferrarilogolight.avif`,
    "Red Bull": `${A}/Red Bull Racing/2025redbullracinglogowhite.avif`,
    McLaren: `${A}/McLaren/2025mclarenlogowhite.avif`,
    "Aston Martin": `${A}/Aston Martin/astonmartinlogo.avif`,
    Alpine: `${A}/Alpine/alpinelogo.avif`,
    Haas: `${A}/Haas F1 Team/2025haaslogowhite.avif`,
    Williams: `${A}/Williams/williamslogo.avif`,
    "Racing Bulls": `${A}/Racing Bulls/2025racingbullslogowhite.avif`,
    Audi: `${A}/Audi/2026audilogowhite.avif`,
    Cadillac: `${A}/Cadillac/2026cadillaclogowhite.avif`,
};

export const TEAM_CARS: Record<string, string> = {
    Mercedes: `${A}/Mercedes/2025mercedescarright.avif`,
    Ferrari: `${A}/Ferrari/2025ferraricarright.avif`,
    "Red Bull": `${A}/Red Bull Racing/2025redbullracingcarright.avif`,
    McLaren: `${A}/McLaren/2025mclarencarright.avif`,
    "Aston Martin": `${A}/Aston Martin/astonmartincar.avif`,
    Alpine: `${A}/Alpine/alpinecar.avif`,
    Haas: `${A}/Haas F1 Team/2025haascarright.avif`,
    Williams: `${A}/Williams/williamscar.avif`,
    "Racing Bulls": `${A}/Racing Bulls/2025racingbullscarright.avif`,
    Audi: `${A}/Audi/2026audicarright.avif`,
    Cadillac: `${A}/Cadillac/2026cadillaccarright.avif`,
};

/** Team display name → colour, derived from the roster above so it can't
 *  drift out of sync with what a driver row actually shows. Used for team
 *  accents (e.g. Teams page card borders) wherever a single representative
 *  hue is needed for a constructor, not a specific driver. */
export const TEAM_COLORS: Record<string, string> = Object.fromEntries(
    DRIVERS.map((d) => [d.team, d.color])
);

const BY_ID = new Map<string, Driver>();
for (const d of DRIVERS) {
    BY_ID.set(d.id, d);
    BY_ID.set(d.code.toLowerCase(), d);
    // Surname, so "verstappen" and "max_verstappen" both resolve.
    BY_ID.set(d.id.split("_").pop()!, d);
    BY_ID.set(d.name.split(" ").pop()!.toLowerCase(), d);
}

/** Look up a driver by id, code or surname. Returns undefined if unknown. */
export function resolveDriver(key: string | undefined | null): Driver | undefined {
    if (!key) return undefined;
    const k = String(key).trim().toLowerCase().replace(/\s+/g, "_");
    return BY_ID.get(k) ?? BY_ID.get(k.split("_").pop()!);
}

/** Display name for an unknown id, rather than rendering a raw slug. */
export function prettyName(key: string): string {
    return resolveDriver(key)?.name ?? key.replace(/_/g, " ").replace(
        /\b\w/g, (c) => c.toUpperCase()
    );
}
