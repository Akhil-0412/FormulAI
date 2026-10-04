/**
 * Circuit map registry.
 *
 * The previous version of this page fuzzy-matched a hardcoded circuit list
 * against filenames at request time (`country.toLowerCase().replace(" ","")`
 * substring-searched into the asset folder). That's the same class of bug
 * that broke the driver avatars — asset filenames were verified directly
 * (`ls`) rather than re-guessed, so this maps to exact, confirmed files.
 *
 * "Is this circuit in this year's competition" is answered from the real
 * 2026 Jolpica schedule, not assumed. Pulling the live calendar surfaced
 * that Bahrain isn't raced in 2026 at all (round 16 runs at Sepang instead)
 * and Madrid is new — a hardcoded circuit list would have gotten both wrong.
 */

const A = "/assets/Circuit";

export type CircuitInfo = {
    slug: string;
    name: string;
    locality: string;
    img: string;
};

/** slug -> asset, verified against the actual folder contents. */
export const CIRCUITS: CircuitInfo[] = [
    { slug: "melbourne", name: "Albert Park Circuit", locality: "Melbourne", img: `${A}/2026trackmelbournedetailed.avif` },
    { slug: "shanghai", name: "Shanghai International Circuit", locality: "Shanghai", img: `${A}/2026trackshanghaidetailed.avif` },
    { slug: "suzuka", name: "Suzuka Circuit", locality: "Suzuka", img: `${A}/2026tracksuzukadetailed.avif` },
    { slug: "miami", name: "Miami International Autodrome", locality: "Miami", img: `${A}/2026trackmiamidetailed.avif` },
    { slug: "montreal", name: "Circuit Gilles Villeneuve", locality: "Montreal", img: `${A}/2026trackmontrealdetailed.avif` },
    { slug: "montecarlo", name: "Circuit de Monaco", locality: "Monte Carlo", img: `${A}/2026trackmontecarlodetailed.avif` },
    { slug: "catalunya", name: "Circuit de Barcelona-Catalunya", locality: "Catalunya", img: `${A}/2026trackcatalunyadetailed.avif` },
    { slug: "spielberg", name: "Red Bull Ring", locality: "Spielberg", img: `${A}/2026trackspielbergdetailed.avif` },
    { slug: "silverstone", name: "Silverstone Circuit", locality: "Silverstone", img: `${A}/2026tracksilverstonedetailed.avif` },
    { slug: "spafrancorchamps", name: "Circuit de Spa-Francorchamps", locality: "Spa", img: `${A}/2026trackspafrancorchampsdetailed.avif` },
    { slug: "hungaroring", name: "Hungaroring", locality: "Budapest", img: `${A}/2026trackhungaroringdetailed.avif` },
    { slug: "zandvoort", name: "Circuit Zandvoort", locality: "Zandvoort", img: `${A}/2026trackzandvoortdetailed.avif` },
    { slug: "monza", name: "Autodromo Nazionale Monza", locality: "Monza", img: `${A}/2026trackmonzadetailed.avif` },
    { slug: "madring", name: "Madring", locality: "Madrid", img: `${A}/2026trackmadringdetailed.avif` },
    { slug: "baku", name: "Baku City Circuit", locality: "Baku", img: `${A}/2026trackbakudetailed.avif` },
    { slug: "singapore", name: "Marina Bay Street Circuit", locality: "Singapore", img: `${A}/2026tracksingaporedetailed.avif` },
    { slug: "austin", name: "Circuit of the Americas", locality: "Austin", img: `${A}/2026trackaustindetailed.avif` },
    { slug: "mexicocity", name: "Autódromo Hermanos Rodríguez", locality: "Mexico City", img: `${A}/2026trackmexicocitydetailed.avif` },
    { slug: "interlagos", name: "Autódromo José Carlos Pace", locality: "Interlagos", img: `${A}/2026trackinterlagosdetailed.avif` },
    { slug: "lasvegas", name: "Las Vegas Strip Circuit", locality: "Las Vegas", img: `${A}/2026tracklasvegasdetailed.avif` },
    { slug: "lusail", name: "Lusail International Circuit", locality: "Lusail", img: `${A}/2026tracklusaildetailed.avif` },
    { slug: "yasmarina", name: "Yas Marina Circuit", locality: "Yas Marina", img: `${A}/2026trackyasmarinacircuitdetailed.avif` },
    // Not on the 2026 calendar, but assets exist — kept as reference/library
    // entries so the page reflects what art is actually available, with the
    // star system (below) making clear these aren't being raced this year.
    { slug: "sakhir", name: "Bahrain International Circuit", locality: "Sakhir", img: `${A}/2026tracksakhirdetailed.avif` },
    { slug: "jeddah", name: "Jeddah Corniche Circuit", locality: "Jeddah", img: `${A}/2026trackjeddahdetailed.avif` },
];

/**
 * Jolpica circuitId -> our slug. Verified against a live 2026 schedule
 * response, not guessed — several of these don't spell out obviously
 * ("villeneuve" is Montreal, "americas" is Austin, "vegas" needs the
 * "las" prefix to match our filename).
 */
export const CIRCUIT_SLUG_BY_JOLPICA_ID: Record<string, string> = {
    albert_park: "melbourne",
    shanghai: "shanghai",
    suzuka: "suzuka",
    miami: "miami",
    villeneuve: "montreal",
    monaco: "montecarlo",
    catalunya: "catalunya",
    red_bull_ring: "spielberg",
    silverstone: "silverstone",
    spa: "spafrancorchamps",
    hungaroring: "hungaroring",
    zandvoort: "zandvoort",
    monza: "monza",
    madring: "madring",
    baku: "baku",
    marina_bay: "singapore",
    americas: "austin",
    rodriguez: "mexicocity",
    interlagos: "interlagos",
    vegas: "lasvegas",
    losail: "lusail",
    yas_marina: "yasmarina",
    bahrain: "sakhir",
    jeddah: "jeddah",
    // sepang (round 16, 2026) has no local asset yet.
};

export type ScheduleEntry = {
    round: number;
    raceName: string;
    date: string;
    circuitId: string;
    lat: number;
    long: number;
};

export async function fetchSeasonSchedule(year: number): Promise<ScheduleEntry[]> {
    const res = await fetch(`https://api.jolpi.ca/ergast/f1/${year}.json?limit=40`);
    const json = await res.json();
    const races = json?.MRData?.RaceTable?.Races ?? [];
    return races.map((r: any) => ({
        round: Number(r.round),
        raceName: r.raceName,
        date: r.date,
        circuitId: r.Circuit?.circuitId ?? "",
        lat: Number(r.Circuit?.Location?.lat ?? 0),
        long: Number(r.Circuit?.Location?.long ?? 0),
    }));
}
