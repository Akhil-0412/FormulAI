"use client";

import { useState, useEffect, useMemo } from "react";
import {
    BrainCircuit, Target, CloudRain, Droplets, MapPin, Thermometer, Wind, Gauge,
    ChevronDown, ChevronUp, AlertTriangle, Timer, Flag, Zap, TrendingUp
} from "lucide-react";
import CinematicPipeline, { PipelineStage } from "./components/CinematicPipeline";
import PodiumStage from "./components/PodiumStage";
import RaceMapPanel from "./components/RaceMapPanel";
import PredictionLog, { LogRound, LogSeason } from "./components/PredictionLog";
import type { RaceResult } from "./components/RaceDossier";
import DriverAvatar from "../components/ui/DriverAvatar";
import type { RaceMapLocation, RaceMapStatus } from "../components/ui/RaceMap";
import { resolveDriver, prettyName, TEAM_LOGOS } from "../constants/drivers";
import {
    CIRCUITS,
    CIRCUIT_SLUG_BY_JOLPICA_ID,
    fetchSeasonSchedule,
    ScheduleEntry,
} from "../lib/circuits";
import { CONSTRUCTOR_NAME } from "../lib/season";

const SEASON = 2026;

/* ═══════════════════════════════════════════════════════════════════════
   TYPES
   ═══════════════════════════════════════════════════════════════════════ */

interface BacktestRace {
    round: number;
    race_name: string;
    predicted: string[];
    actual: string[];
    correct: number;
    brier_score: number;
    probabilities: Record<string, number>;
    is_future?: boolean;
}

interface SimulationLog {
    id: number;
    message: string;
    status: 'pending' | 'running' | 'done' | 'error';
}

interface FullRaceWeather {
    temperature: number | null;
    precipitation_prob: number | null;
    wind_speed: number | null;
    humidity: number | null;
    condition: string;
}

interface CircuitInfo {
    circuit_id: string;
    circuit_type: string;
    overtake_difficulty: number;
    laps: number;
    lap_distance_km: number;
}

interface ModelParameter {
    name: string;
    description: string;
    category: string;
    impact: string;
}

interface FeatureAttribution {
    feature: string;
    shap_value: number;
    value: number;
    direction: "positive" | "negative";
}

interface AlternativeDriverSchema {
    driver_id: string;
    probability: number;
    gap_to_podium: number;
}

interface FullGridDriver {
    position: number;
    driver_id: string;
    podium_probability: number;
    p1_probability: number;
    p2_probability: number;
    p3_probability: number;
    expected_lap_time_sec: number | null;
    dnf_risk: number;
    dnf_note: string;
    constructor_id: string;
    reasoning?: string;
    top_features?: FeatureAttribution[];
}

interface FullRaceResponse {
    race: { race_id: string; year: number; round: number; circuit_name: string; country: string; race_date: string };
    weather: FullRaceWeather;
    circuit: CircuitInfo;
    parameters: ModelParameter[];
    full_grid: FullGridDriver[];
    podium: string[];
    confidence_level: string;
    n_simulations: number;
    upset_probability?: number;
    alternatives?: AlternativeDriverSchema[];
}

/* ═══════════════════════════════════════════════════════════════════════
   DRIVER / TEAM DATA
   ═══════════════════════════════════════════════════════════════════════ */

/**
 * Driver/team identity now routes through the shared registry
 * (`resolveDriver` / `TEAM_LOGOS` from constants/drivers.ts, `CONSTRUCTOR_NAME`
 * from lib/season.ts) rather than a fourth local copy. The previous local
 * map here had two live bugs: Pérez and Bottas had `img: ""` (no photo at
 * all — always fell to the 👤 placeholder), and a `tsunoda` entry was
 * mislabeled with Arvid Lindblad's name and photo — a genuine
 * wrong-identity bug, not just a stale crop.
 *
 * `CONSTRUCTOR_NAME` only covers the current 11 teams; a couple of aliases
 * are kept here for older backtest rows that predate a team rename
 * (Sauber → Audi, AlphaTauri → Racing Bulls).
 */
const LEGACY_CONSTRUCTOR_ALIASES: Record<string, string> = {
    sauber: "Audi",
    alphatauri: "Racing Bulls",
};

const getTeamFromConstructor = (cid: string) =>
    CONSTRUCTOR_NAME[cid] ??
    LEGACY_CONSTRUCTOR_ALIASES[cid] ??
    cid.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

const IMPACT_COLORS: Record<string, string> = {
    HIGH: "text-red-400 bg-red-500/10 border-red-500/30",
    MEDIUM: "text-amber-400 bg-amber-500/10 border-amber-500/30",
    LOW: "text-blue-400 bg-blue-500/10 border-blue-500/30",
};

const CATEGORY_ICONS: Record<string, string> = {
    weather: "🌤️", driver_form: "🏎️", track: "🏁", constructor: "🏢", qualifying: "⏱️",
};

/* ═══════════════════════════════════════════════════════════════════════
   PAGE COMPONENT
   ═══════════════════════════════════════════════════════════════════════ */

/** Backtests that exist for years before the live season, oldest first. */
const PRIOR_SEASONS = [2024, 2025];

export default function PredictionsPage() {
    const [backtestData, setBacktestData] = useState<BacktestRace[]>([]);
    // Prior seasons are read-only history for the log tree — nothing else
    // on the page (the map, the pipeline, "next race") reasons about them,
    // so they get their own state rather than joining backtestData.
    const [priorSeasons, setPriorSeasons] = useState<LogSeason[]>([]);
    const [fullRace, setFullRace] = useState<FullRaceResponse | null>(null);
    const [pipelineStage, setPipelineStage] = useState<PipelineStage>("idle");
    const [showFullGrid, setShowFullGrid] = useState(false);
    const [showParams, setShowParams] = useState(false);
    // The reveal is podium-only by default (weather/params/alternatives/full
    // grid are real, useful data, but shouldn't compete with the reveal
    // moment itself) — this gates all of it behind one toggle underneath
    // the podium stage.
    const [showBreakdown, setShowBreakdown] = useState(false);
    // upcomingResult: the future race entry to show after animation completes
    const [upcomingResult, setUpcomingResult] = useState<BacktestRace | null>(null);

    // The season map needs real circuit coordinates, which only the live
    // schedule has — the backtest payload carries results, not geography.
    const [schedule, setSchedule] = useState<ScheduleEntry[]>([]);

    useEffect(() => {
        fetch("/data/rolling_backtest_2026.json")
            .then(res => res.json())
            .then(data => setBacktestData(data))
            .catch(err => console.error("Backtest load failed:", err));
    }, []);

    /* Prior seasons' backtests are static, already-settled snapshots — no
       "future" round to gate on, so anything with a real 3-driver podium
       counts as scored. A year whose file doesn't exist (nothing's been
       backtested there yet) is just left out rather than shown empty. */
    useEffect(() => {
        Promise.all(
            PRIOR_SEASONS.map((year) =>
                fetch(`/data/rolling_backtest_${year}.json`)
                    .then((res) => (res.ok ? res.json() : null))
                    .then((data: BacktestRace[] | null) =>
                        data
                            ? {
                                  season: year,
                                  rounds: data
                                      .filter((r) => r.actual && r.actual.length >= 3)
                                      .map((r) => ({
                                          round: r.round,
                                          raceName: r.race_name,
                                          correct: r.correct,
                                          brierScore: r.brier_score,
                                          predicted: r.predicted,
                                          actual: r.actual,
                                          probabilities: r.probabilities ?? {},
                                      })),
                              }
                            : null
                    )
                    .catch(() => null)
            )
        ).then((results) =>
            setPriorSeasons(
                results.filter((s): s is LogSeason => s !== null && s.rounds.length > 0)
            )
        );
    }, []);

    useEffect(() => {
        fetchSeasonSchedule(SEASON)
            .then(setSchedule)
            .catch(err => console.error("Season schedule load failed:", err));
    }, []);

    /**
     * Season map markers.
     *
     * Position comes from the schedule, naming from the circuit registry,
     * and "where in the season are we" from the backtest's own future
     * round — not from today's date. The page's whole narrative is the
     * model's position in the season, so a round the backtest hasn't
     * reached yet reads as upcoming here even if its calendar date has
     * already passed. The date fallback only applies before the backtest
     * has loaded.
     */
    const mapLocations = useMemo<RaceMapLocation[]>(() => {
        const backtestByRound = new Map(backtestData.map(r => [r.round, r]));
        const nextRound = backtestData.find(r => r.is_future)?.round;
        const today = new Date();

        return schedule
            .filter(entry => entry.lat !== 0 || entry.long !== 0)
            .map(entry => {
                const circuit = CIRCUITS.find(
                    c => c.slug === CIRCUIT_SLUG_BY_JOLPICA_ID[entry.circuitId]
                );
                const backtest = backtestByRound.get(entry.round);

                const status: RaceMapStatus =
                    nextRound == null
                        ? new Date(entry.date) < today ? "completed" : "upcoming"
                        : entry.round === nextRound ? "next"
                        : entry.round < nextRound ? "completed"
                        : "upcoming";

                const raced = backtest && backtest.actual?.length >= 3;

                return {
                    slug: circuit?.slug ?? `round-${entry.round}`,
                    name: circuit?.name ?? entry.raceName,
                    locality: circuit?.locality ?? entry.raceName.replace(/ Grand Prix$/, ""),
                    lat: entry.lat,
                    long: entry.long,
                    round: entry.round,
                    date: entry.date,
                    status,
                    note: raced
                        ? `${backtest!.correct}/3 podium places called`
                        : undefined,
                };
            });
    }, [schedule, backtestData]);

    /**
     * Scored rounds, keyed by map slug — clicking one of these markers on
     * the expanded map opens its dossier. Rounds the model hasn't reached
     * are simply absent, which is what makes their markers name-only.
     */
    const mapResults = useMemo<Record<string, RaceResult>>(() => {
        const backtestByRound = new Map(backtestData.map(r => [r.round, r]));
        const out: Record<string, RaceResult> = {};

        for (const location of mapLocations) {
            const backtest =
                location.round != null ? backtestByRound.get(location.round) : undefined;
            if (!backtest || !backtest.actual || backtest.actual.length < 3) continue;

            out[location.slug] = {
                predicted: backtest.predicted,
                actual: backtest.actual,
                correct: backtest.correct,
                brierScore: backtest.brier_score,
                probabilities: backtest.probabilities ?? {},
            };
        }
        return out;
    }, [mapLocations, backtestData]);

    const runPrediction = async () => {
        // Reset previous result
        setUpcomingResult(null);
        setFullRace(null);
        setShowFullGrid(false);
        setPipelineStage("ingesting");

        // Stage 1: Ingesting (2 seconds)
        await new Promise(r => setTimeout(r, 2000));
        setPipelineStage("processing");

        // Stage 2: Processing (2 seconds)
        await new Promise(r => setTimeout(r, 2000));
        setPipelineStage("calibrating");

        // Stage 3: Calibrating (1.5 seconds)
        await new Promise(r => setTimeout(r, 1500));
        setPipelineStage("complete");

        // Allow the exit animation to play, then reveal the result
        setTimeout(() => {
            // Use the first future race from the backtest data
            const future = backtestData.find(r => !r.actual || r.actual.length < 3);
            if (future) setUpcomingResult(future);
            setPipelineStage("idle");
        }, 600);
    };

    // Separate completed and future races
    const completedRaces = backtestData.filter(r => r.actual && r.actual.length >= 3).reverse();
    const futureRaces = backtestData.filter(r => !r.actual || r.actual.length < 3);

    // Backtest aggregate stats (only completed races)
    const totalCorrect = completedRaces.reduce((s, r) => s + r.correct, 0);
    const totalPossible = completedRaces.length * 3;
    const overallAccuracy = totalPossible > 0 ? ((totalCorrect / totalPossible) * 100).toFixed(1) : "0";
    const perfectRaces = completedRaces.filter(r => r.correct === 3).length;
    const avgBrier = completedRaces.length > 0
        ? (completedRaces.reduce((s, r) => s + r.brier_score, 0) / completedRaces.length).toFixed(4) : "0";

    /* The log tree wants scored rounds newest-first alongside whatever's
       still ahead, so the reader lands on the most recent result and can
       scroll down into history rather than up from round 1. */
    const logRounds: LogRound[] = [...backtestData]
        .sort((a, b) => b.round - a.round)
        .map((r) => ({
            round: r.round,
            raceName: r.race_name,
            correct: r.correct,
            brierScore: r.brier_score,
            predicted: r.predicted,
            actual: r.actual,
            probabilities: r.probabilities ?? {},
            isFuture: !r.actual || r.actual.length < 3,
        }));

    /* Live season first (it's the one the reader almost certainly wants
       open), then prior years newest-first underneath it. */
    const logSeasons: LogSeason[] = [
        { season: SEASON, rounds: logRounds },
        ...[...priorSeasons].sort((a, b) => b.season - a.season),
    ];

    return (
        <div className="w-full">
            <div className="flex flex-col gap-10 max-w-[1500px] mx-auto pb-20 px-4">
                {/* ═════════════════════════════════════════════════════════
                   2026 RACE DAY PREDICTION
                   ═════════════════════════════════════════════════════════ */}
                <section className="flex flex-col gap-6 pt-10">
                    {(() => {
                        const nextRace = backtestData.find(r => r.is_future);
                        const raceLabel = nextRace ? nextRace.race_name : "2026 Race Prediction";
                        return (
                            /* Race identity on the left, the season map on
                               the right — the map answers the other half of
                               "which race is this", so it belongs in the
                               header band rather than as a section of its
                               own. Keeping it to roughly a third of the row
                               is also what makes the expansion worth doing:
                               a full-width preview has nowhere to grow. */
                            <div className="flex flex-col lg:flex-row lg:items-stretch gap-5">
                                <div className="flex-1 flex flex-col justify-between gap-5">
                                    <div>
                                        <h2 className="h-section text-fg flex items-center gap-3">
                                            <Flag className="w-6 h-6 text-accent" />
                                            {raceLabel} — Prediction
                                        </h2>
                                        <p className="label-xs mt-1.5">
                                            {nextRace ? `Round ${nextRace.round} · 2026 Season` : "2026 Formula 1 Season"}
                                        </p>
                                    </div>
                                    <button
                                        onClick={runPrediction}
                                        disabled={pipelineStage !== "idle"}
                                        className={`self-start px-7 py-3.5 rounded-[var(--radius-chip)] font-bold text-[15px] transition-colors whitespace-nowrap ${pipelineStage !== "idle"
                                            ? "bg-ink-3 cursor-not-allowed text-fg-subtle"
                                            : "bg-accent hover:bg-accent-hot text-white"
                                            }`}
                                    >
                                        {pipelineStage !== "idle" ? "Engine running…" : "Run prediction"}
                                    </button>
                                </div>

                                {/* ── SEASON MAP ────────────────────────
                                   Click expands it into a focused overlay
                                   over this page; it never navigates. */}
                                {mapLocations.length > 0 && (
                                    <div className="w-full lg:w-[42%] lg:max-w-[620px] shrink-0">
                                        <RaceMapPanel
                                            locations={mapLocations}
                                            season={SEASON}
                                            results={mapResults}
                                        />
                                    </div>
                                )}
                            </div>
                        );
                    })()}

                    {/* Cinematic Prediction Pipeline */}
                    <CinematicPipeline stage={pipelineStage} />

                {/* ── UPCOMING RESULT — shown after animation completes ── */}
                {upcomingResult && (
                    <div className="flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
                        <PodiumStage
                            raceName={upcomingResult.race_name}
                            podium={upcomingResult.predicted.slice(0, 3).map((driverId) => ({
                                driverId,
                                probability: upcomingResult.probabilities?.[driverId] ?? null,
                            }))}
                        />
                    </div>
                )}

                {/* ── RESULTS ───────────────────────────────────────────── */}
                {fullRace && (
                    <div className="flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-4 duration-700">

                        {/* ── PODIUM REVEAL — the only thing shown at first ── */}
                        <PodiumStage
                            raceName={`${fullRace.race.circuit_name} — ${fullRace.race.country}`}
                            podium={fullRace.podium.slice(0, 3).map((driverId) => {
                                const entry = fullRace.full_grid.find((g) => g.driver_id === driverId);
                                const rank = fullRace.podium.indexOf(driverId);
                                const prob = entry
                                    ? rank === 0 ? entry.p1_probability : rank === 1 ? entry.p2_probability : entry.p3_probability
                                    : null;
                                return { driverId, probability: prob };
                            })}
                        />

                        <button
                            onClick={() => setShowBreakdown((v) => !v)}
                            className="self-center flex items-center gap-1.5 text-[13px] font-semibold text-fg-muted hover:text-fg transition-colors"
                        >
                            {showBreakdown ? (
                                <>Hide full breakdown <ChevronUp className="w-4 h-4" /></>
                            ) : (
                                <>Show full breakdown — weather, model inputs, full grid <ChevronDown className="w-4 h-4" /></>
                            )}
                        </button>

                        {showBreakdown && (
                        <div className="flex flex-col gap-8 animate-in fade-in slide-in-from-top-2 duration-300">

                        {/* ── Weather & Circuit ───────────────────────── */}
                        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                            <WeatherCard icon={<Thermometer className="w-5 h-5" />} label="Temperature" value={fullRace.weather?.temperature != null ? `${fullRace.weather.temperature}°C` : "N/A"} />
                            <WeatherCard icon={<CloudRain className="w-5 h-5" />} label="Rain Chance" value={fullRace.weather?.precipitation_prob != null ? `${fullRace.weather.precipitation_prob}%` : "N/A"} highlight={fullRace.weather?.precipitation_prob != null && fullRace.weather.precipitation_prob > 40} />
                            <WeatherCard icon={<Wind className="w-5 h-5" />} label="Wind Speed" value={fullRace.weather?.wind_speed != null ? `${fullRace.weather.wind_speed} km/h` : "N/A"} />
                            <WeatherCard icon={<Droplets className="w-5 h-5" />} label="Humidity" value={fullRace.weather?.humidity != null ? `${fullRace.weather.humidity}%` : "N/A"} />
                            <WeatherCard icon={<MapPin className="w-5 h-5" />} label="Track Type" value={fullRace.circuit.circuit_type.charAt(0).toUpperCase() + fullRace.circuit.circuit_type.slice(1)} />
                            <WeatherCard icon={<Gauge className="w-5 h-5" />} label="Overtake Diff." value={`${(fullRace.circuit.overtake_difficulty * 100).toFixed(0)}%`} highlight={fullRace.circuit.overtake_difficulty > 0.5} />
                        </div>

                        <div className="flex items-center gap-4 text-sm text-f1-muted">
                            <span className="flex items-center gap-1"><Timer className="w-4 h-4" /> {fullRace.circuit.laps} Laps</span>
                            <span>·</span>
                            <span>{fullRace.circuit.lap_distance_km} km/lap</span>
                            <span>·</span>
                            <span>{(fullRace.circuit.laps * fullRace.circuit.lap_distance_km).toFixed(1)} km total</span>
                            <span>·</span>
                            <span>{fullRace.n_simulations.toLocaleString()} Monte Carlo simulations</span>
                        </div>

                        {/* ── Model Parameters (collapsible) ─────────── */}
                        <div className="glass-card overflow-hidden">
                            <button
                                className="w-full flex items-center justify-between p-5 text-left hover:bg-white/5 transition-colors"
                                onClick={() => setShowParams(!showParams)}
                            >
                                <div className="flex items-center gap-3">
                                    <BrainCircuit className="w-6 h-6 text-purple-400" />
                                    <span className="text-lg font-bold text-white">Model Input Parameters</span>
                                    <span className="text-xs text-f1-muted px-2 py-0.5 rounded-full bg-white/10">{fullRace.parameters.length} features</span>
                                </div>
                                {showParams ? <ChevronUp className="w-5 h-5 text-f1-muted" /> : <ChevronDown className="w-5 h-5 text-f1-muted" />}
                            </button>
                            {showParams && (
                                <div className="px-5 pb-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                    {fullRace.parameters.map((p, i) => (
                                        <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-white/5 border border-white/5">
                                            <span className="text-xl mt-0.5">{CATEGORY_ICONS[p.category] || "📊"}</span>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm font-bold text-white truncate">{p.name}</span>
                                                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${IMPACT_COLORS[p.impact]}`}>{p.impact}</span>
                                                </div>
                                                <p className="text-xs text-f1-muted mt-0.5 leading-relaxed">{p.description}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* ── DETAILED PODIUM — per-driver SHAP reasoning, DNF risk ── */}
                        <div className="relative">
                            <div className="glass-card p-8 relative overflow-hidden">
                                <h3 className="text-xs font-bold text-f1-muted uppercase tracking-[0.3em] mb-8 text-center">
                                    Podium breakdown — model reasoning per driver
                                </h3>

                                <div className="flex flex-col md:flex-row items-start justify-center gap-4 md:gap-6">
                                    {/* P2 */}
                                    {fullRace.podium[1] && <PodiumCard driverId={fullRace.podium[1]} position={2} grid={fullRace.full_grid} constructorId={fullRace.full_grid.find(d => d.driver_id === fullRace.podium[1])?.constructor_id || ""} />}
                                    {/* P1 */}
                                    {fullRace.podium[0] && <PodiumCard driverId={fullRace.podium[0]} position={1} grid={fullRace.full_grid} constructorId={fullRace.full_grid.find(d => d.driver_id === fullRace.podium[0])?.constructor_id || ""} />}
                                    {/* P3 */}
                                    {fullRace.podium[2] && <PodiumCard driverId={fullRace.podium[2]} position={3} grid={fullRace.full_grid} constructorId={fullRace.full_grid.find(d => d.driver_id === fullRace.podium[2])?.constructor_id || ""} />}
                                </div>
                            </div>
                        </div>

                        {/* ── EXPLAINABILITY / ALTERNATIVES ───────────────────────────── */}
                        {fullRace.alternatives && fullRace.alternatives.length > 0 && (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-in fade-in slide-in-from-bottom-4 duration-1000 delay-300">
                                <div className="md:col-span-2 glass-card p-6 border border-amber-500/20">
                                    <h3 className="text-amber-400 font-bold uppercase tracking-wider text-xs mb-4 flex items-center gap-2">
                                        <AlertTriangle className="w-4 h-4" /> Drivers on the Bubble
                                    </h3>
                                    <div className="flex flex-col gap-3">
                                        {fullRace.alternatives.map((alt, i) => {
                                            const drv = resolveDriver(alt.driver_id);
                                            return (
                                                <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors">
                                                    <div className="flex items-center gap-3">
                                                        <div className="text-sm font-bold text-white/50 w-6">P{i + 4}</div>
                                                        <DriverAvatar driverKey={alt.driver_id} size={32} />
                                                        <div>
                                                            <div className="text-white font-bold text-sm">{drv?.name ?? prettyName(alt.driver_id)}</div>
                                                            <div className="text-[10px] text-f1-muted uppercase">{drv?.team ?? "—"}</div>
                                                        </div>
                                                    </div>
                                                    <div className="text-right">
                                                        <div className="text-sm font-mono text-white">{(alt.probability * 100).toFixed(1)}%</div>
                                                        <div className="text-[10px] text-red-400 font-mono">-{ (alt.gap_to_podium * 100).toFixed(1) }% to P3</div>
                                                    </div>
                                                </div>
                                            )
                                        })}
                                    </div>
                                </div>
                                <div className="glass-card p-6 flex flex-col justify-center items-center text-center border border-red-500/20 bg-gradient-to-b from-transparent to-red-900/10">
                                    <h3 className="text-red-400 font-bold uppercase tracking-wider text-xs mb-2">Upset Alert</h3>
                                    <p className="text-f1-muted text-xs mb-4">Chance of unpredicted driver stealing podium</p>
                                    <div className="text-5xl font-black text-white font-mono mb-2">
                                        {((fullRace.upset_probability || 0) * 100).toFixed(1)}<span className="text-2xl text-white/50">%</span>
                                    </div>
                                    <div className="w-full bg-white/10 h-2 rounded-full overflow-hidden mt-2">
                                        <div className="bg-gradient-to-r from-amber-500 to-red-600 h-full" style={{ width: `${Math.min((fullRace.upset_probability || 0) * 100 * 2, 100)}%` }} />
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* ── FULL GRID ──────────────────────────────── */}
                        <div className="glass-card overflow-hidden">
                            <button
                                className="w-full flex items-center justify-between p-5 text-left hover:bg-white/5 transition-colors"
                                onClick={() => setShowFullGrid(!showFullGrid)}
                            >
                                <div className="flex items-center gap-3">
                                    <Target className="w-6 h-6 text-emerald-400" />
                                    <span className="text-lg font-bold text-white">Full Race Prediction — All {fullRace.full_grid.length} Drivers</span>
                                </div>
                                {showFullGrid ? <ChevronUp className="w-5 h-5 text-f1-muted" /> : <ChevronDown className="w-5 h-5 text-f1-muted" />}
                            </button>

                            {showFullGrid && (
                                <div className="px-5 pb-5 flex flex-col gap-2">
                                    {fullRace.full_grid.map((driver) => {
                                        const drv = resolveDriver(driver.driver_id);
                                        const teamName = drv?.team ?? getTeamFromConstructor(driver.constructor_id);
                                        const logo = TEAM_LOGOS[teamName];
                                        const isPodium = driver.position <= 3;
                                        const isPoints = driver.position <= 10;

                                        const posColor = isPodium
                                            ? driver.position === 1 ? "text-yellow-400" : driver.position === 2 ? "text-gray-300" : "text-amber-600"
                                            : isPoints ? "text-blue-400" : "text-f1-muted";

                                        return (
                                            <div key={driver.driver_id}
                                                className={`flex items-center gap-4 p-3 rounded-lg transition-all hover:bg-white/5 ${isPodium ? "bg-white/5 border border-white/10" : "border border-transparent"}`}
                                            >
                                                {/* Position */}
                                                <div className={`text-2xl font-black w-10 text-center ${posColor}`}>
                                                    {driver.position}
                                                </div>

                                                {/* Driver Image */}
                                                <DriverAvatar driverKey={driver.driver_id} size={48} />

                                                {/* Name + Team */}
                                                <div className="flex flex-col flex-1 min-w-0">
                                                    <span className="font-bold text-white text-sm truncate">{drv?.name ?? prettyName(driver.driver_id)}</span>
                                                    <div className="flex items-center gap-2">
                                                        {logo && <img src={logo} className="h-3 object-contain brightness-0 invert opacity-50" alt={teamName} />}
                                                        <span className="text-[10px] text-f1-muted uppercase tracking-wider truncate">{teamName}</span>
                                                    </div>
                                                </div>

                                                {/* Podium Probability */}
                                                <div className="text-right min-w-[60px] hidden md:block">
                                                    <span className="text-xs text-f1-muted">Podium</span>
                                                    <span className={`block text-sm font-mono font-bold ${driver.podium_probability > 0.5 ? "text-emerald-400" : driver.podium_probability > 0.1 ? "text-amber-400" : "text-f1-muted"}`}>
                                                        {(driver.podium_probability * 100).toFixed(1)}%
                                                    </span>
                                                </div>

                                                {/* Lap Time */}
                                                <div className="text-right min-w-[70px] hidden lg:block">
                                                    <span className="text-xs text-f1-muted">Est. Lap</span>
                                                    <span className="block text-sm font-mono text-white/80">
                                                        {driver.expected_lap_time_sec ? `${Math.floor(driver.expected_lap_time_sec / 60)}:${(driver.expected_lap_time_sec % 60).toFixed(3).padStart(6, "0")}` : "—"}
                                                    </span>
                                                </div>

                                                {/* DNF Risk */}
                                                <div className="text-right min-w-[80px]">
                                                    <span className="text-xs text-f1-muted">DNF Risk</span>
                                                    <div className="flex items-center justify-end gap-1">
                                                        {driver.dnf_risk > 0.15 && <AlertTriangle className="w-3 h-3 text-amber-400" />}
                                                        <span className={`text-sm font-mono font-bold ${driver.dnf_risk > 0.15 ? "text-red-400" : driver.dnf_risk > 0.08 ? "text-amber-400" : "text-emerald-400"}`}>
                                                            {(driver.dnf_risk * 100).toFixed(0)}%
                                                        </span>
                                                    </div>
                                                    <span className="text-[9px] text-f1-muted truncate block max-w-[120px]">{driver.dnf_note}</span>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                        </div>
                        )}
                    </div>
                )}
            </section>

            {/* ═════════════════════════════════════════════════════════════
               MODEL VALIDATION — 2026 Backtest
               ═════════════════════════════════════════════════════════════ */}
            <section className="flex flex-col gap-6 pt-8 border-t border-white/10">
                <div className="flex items-center gap-3">
                    <TrendingUp className="w-6 h-6 text-emerald-400" />
                    <h2 className="text-2xl font-bold text-white">Model Validation — 2026 Season (Unseen Data)</h2>
                </div>
                <p className="text-f1-muted text-sm -mt-4">
                    Trained on 2018–2025 · Rolling retrain after each race · Predicting the 2026 season the model has never seen
                </p>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-[#111118] border border-white/10 rounded-xl p-6 text-center shadow-lg transition-all hover:border-white/20 hover:-translate-y-1 hover:shadow-[0_8px_30px_rgba(16,185,129,0.15)] group">
                        <p className="text-[11px] text-f1-muted uppercase tracking-[0.2em] mb-2 font-bold group-hover:text-white/70 transition-colors">Overall Accuracy</p>
                        <p className="text-4xl font-black text-emerald-400 font-mono tracking-tighter drop-shadow-[0_0_12px_rgba(16,185,129,0.4)]">{overallAccuracy}%</p>
                    </div>
                    <div className="bg-[#111118] border border-white/10 rounded-xl p-6 text-center shadow-lg transition-all hover:border-white/20 hover:-translate-y-1 hover:shadow-[0_8px_30px_rgba(251,191,36,0.15)] group">
                        <p className="text-[11px] text-f1-muted uppercase tracking-[0.2em] mb-2 font-bold group-hover:text-white/70 transition-colors">Perfect Podiums</p>
                        <p className="text-4xl font-black text-amber-400 font-mono tracking-tighter drop-shadow-[0_0_12px_rgba(251,191,36,0.4)]">{perfectRaces}</p>
                    </div>
                    <div className="bg-[#111118] border border-white/10 rounded-xl p-6 text-center shadow-lg transition-all hover:border-white/20 hover:-translate-y-1 hover:shadow-[0_8px_30px_rgba(96,165,250,0.15)] group">
                        <p className="text-[11px] text-f1-muted uppercase tracking-[0.2em] mb-2 font-bold group-hover:text-white/70 transition-colors">Avg Brier Score</p>
                        <p className="text-4xl font-black text-blue-400 font-mono tracking-tighter drop-shadow-[0_0_12px_rgba(96,165,250,0.4)]">{avgBrier}</p>
                    </div>
                    <div className="bg-[#111118] border border-white/10 rounded-xl p-6 text-center shadow-lg transition-all hover:border-white/20 hover:-translate-y-1 hover:shadow-[0_8px_30px_rgba(255,255,255,0.1)] group">
                        <p className="text-[11px] text-f1-muted uppercase tracking-[0.2em] mb-2 font-bold group-hover:text-white/70 transition-colors">Races Evaluated</p>
                        <p className="text-4xl font-black text-white font-mono tracking-tighter drop-shadow-[0_0_12px_rgba(255,255,255,0.3)]">{completedRaces.length}</p>
                    </div>
                </div>

                {/* Per-race breakdown now lives in the season map above:
                    click any raced (green) marker to open that round's
                    dossier — actual podium, model's call, and confidence per
                    driver. Repeating it here as a scrolling stack of cards
                    was the same data twice, and its "race timings" toggle
                    was permanently stuck on placeholder TBA text since that
                    telemetry was never in the backtest payload. */}
                {completedRaces.length > 0 && (
                    <p className="text-[13px] text-fg-muted -mt-2">
                        Click a raced round on the season map above for the
                        full breakdown — actual podium, the model's call, and
                        its confidence for every driver.
                    </p>
                )}
            </section>

            {/* ═════════════════════════════════════════════════════════
               PREDICTION LOG
               The full record behind the stats above: every scored round,
               browsable season → round → the model's ranked field against
               who actually finished on the podium.
               ═════════════════════════════════════════════════════════ */}
            {logSeasons.some((s) => s.rounds.length > 0) && (
                <section className="flex flex-col gap-4">
                    <div>
                        <h2 className="h-section text-fg">Prediction log</h2>
                        <p className="label-xs mt-1">
                            Every round's full field, ranked by the odds the
                            model gave it — expand a round to see how close
                            the ranking landed against who actually podiumed
                        </p>
                    </div>
                    <PredictionLog seasons={logSeasons} />
                </section>
            )}
            </div>
        </div>
    );
}

/* ═══════════════════════════════════════════════════════════════════════
   SUB - COMPONENTS
   ═══════════════════════════════════════════════════════════════════════ */

function WeatherCard({ icon, label, value, highlight }: { icon: React.ReactNode; label: string; value: string; highlight?: boolean }) {
    return (
        <div className={`glass-panel rounded-xl p-3 flex items-center gap-3 ${highlight ? "border border-amber-500/30 bg-amber-500/5" : ""}`}>
            <div className={`${highlight ? "text-amber-400" : "text-f1-muted"}`}>{icon}</div>
            <div>
                <p className="text-[10px] text-f1-muted uppercase tracking-wider">{label}</p>
                <p className={`text-sm font-bold ${highlight ? "text-amber-400" : "text-white"}`}>{value}</p>
            </div>
        </div>
    );
}

function PodiumCard({ driverId, position, grid, constructorId }: { driverId: string; position: number; grid: FullGridDriver[]; constructorId: string }) {
    const drv = resolveDriver(driverId);
    const teamName = drv?.team ?? getTeamFromConstructor(constructorId);
    const logo = TEAM_LOGOS[teamName];
    const gridEntry = grid.find(g => g.driver_id === driverId);
    const [showReasoning, setShowReasoning] = useState(false);

    const heights: Record<number, string> = { 1: "md:order-2", 2: "md:order-1", 3: "md:order-3" };
    const sizes: Record<number, number> = { 1: 128, 2: 104, 3: 92 };
    const medals: Record<number, string> = { 1: "🥇", 2: "🥈", 3: "🥉" };
    const ringColor: Record<number, string> = { 1: "#facc15", 2: "#d1d5db", 3: "#d97706" };

    return (
        <div className={`flex flex-col items-center gap-3 w-full md:w-[30%] ${heights[position]}`}>
            <div className="text-4xl">{medals[position]}</div>
            {/* Medal colour (gold/silver/bronze), not team colour — a podium
                position should read as 1st/2nd/3rd at a glance regardless of
                which team is standing on it. */}
            <div
                className="rounded-full p-1"
                style={{ backgroundColor: ringColor[position] }}
            >
                <DriverAvatar driverKey={driverId} size={sizes[position]} />
            </div>
            <div className="text-center w-full">
                <p className="text-lg font-black text-white">{drv?.name ?? prettyName(driverId)}</p>
                <div className="flex items-center justify-center gap-2 mt-1">
                    {logo && <img src={logo} className="h-4 object-contain brightness-0 invert opacity-70" alt={teamName} />}
                    <span className="text-xs text-f1-muted uppercase tracking-wider">{teamName}</span>
                </div>
            </div>
            <div className="flex gap-3 mt-1 justify-center w-full">
                <div className="text-center">
                    <span className="text-xs text-f1-muted">P{position} Prob</span>
                    <p className="text-lg font-black text-emerald-400 font-mono">
                        {gridEntry ? `${(position === 1 ? gridEntry.p1_probability : position === 2 ? gridEntry.p2_probability : gridEntry.p3_probability) * 100}`.substring(0, 4) + "%" : "—"}
                    </p>
                </div>
                <div className="text-center border-l border-white/10 pl-3">
                    <span className="text-xs text-f1-muted">DNF Risk</span>
                    <p className={`text-lg font-black font-mono ${gridEntry && gridEntry.dnf_risk > 0.1 ? "text-amber-400" : "text-emerald-400"}`}>
                        {gridEntry ? `${(gridEntry.dnf_risk * 100).toFixed(0)}%` : "—"}
                    </p>
                </div>
            </div>

            {/* Model Reasoning Expander */}
            {gridEntry?.top_features && gridEntry.top_features.length > 0 && (
                <div className="w-full mt-4 glass-panel rounded-xl overflow-hidden text-left border border-white/5 transition-all">
                    <button 
                        onClick={() => setShowReasoning(!showReasoning)}
                        className="w-full px-4 py-2 flex items-center justify-between text-xs font-bold text-white/70 hover:bg-white/5 hover:text-white transition-colors"
                    >
                        <span className="flex items-center gap-2"><Zap className="w-3 h-3 text-emerald-400"/> See Model Reasoning</span>
                        {showReasoning ? <ChevronUp className="w-3 h-3"/> : <ChevronDown className="w-3 h-3"/>}
                    </button>
                    {showReasoning && (
                        <div className="px-4 pb-4 pt-1 border-t border-white/5 animate-in slide-in-from-top-2 duration-300">
                            {gridEntry.reasoning && (
                                <p className="text-[10px] text-f1-muted font-mono leading-relaxed mb-3 p-2 bg-black/40 rounded-lg">
                                    {gridEntry.reasoning}
                                </p>
                            )}
                            <div className="space-y-2">
                                <div className="text-[10px] uppercase tracking-wider text-f1-muted mb-1">Top SHAP Features</div>
                                {gridEntry.top_features.map((feat, idx) => {
                                    const isPos = feat.direction === "positive";
                                    // Scale width relative to the largest absolute SHAP value
                                    const maxShap = Math.max(...gridEntry.top_features!.map(f => Math.abs(f.shap_value)));
                                    const pct = Math.max(5, (Math.abs(feat.shap_value) / maxShap) * 100);
                                    
                                    return (
                                        <div key={idx} className="flex flex-col gap-1">
                                            <div className="flex justify-between items-end">
                                                <span className="text-[10px] text-white/90 truncate mr-2" title={feat.feature}>
                                                    {feat.feature.replace(/_/g, ' ')}
                                                </span>
                                                <span className={`text-[10px] font-mono ${isPos ? "text-emerald-400" : "text-red-400"}`}>
                                                    {isPos ? "+" : "-"}{Math.abs(feat.shap_value).toFixed(2)}
                                                </span>
                                            </div>
                                            <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
                                                <div 
                                                    className={`h-full rounded-full ${isPos ? "bg-emerald-500" : "bg-red-500"}`}
                                                    style={{ width: `${pct}%`, opacity: 0.7 + (0.3 * (pct/100)) }}
                                                />
                                            </div>
                                        </div>
                                    )
                                })}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

const UPCOMING_CARD_STYLES: Record<number, { glow: string; order: string; scale: string; badge: string; badgeColor: string }> = {
    1: { glow: "#facc15", order: "md:order-2", scale: "scale-100 z-10 md:scale-110 md:-translate-y-6", badge: "1", badgeColor: "#facc15" },
    2: { glow: "#e5e7eb", order: "md:order-1", scale: "scale-95 z-0 md:scale-100 md:translate-y-4", badge: "2", badgeColor: "#e5e7eb" },
    3: { glow: "#d97706", order: "md:order-3", scale: "scale-90 z-0 md:scale-95 md:translate-y-8", badge: "3", badgeColor: "#d97706" },
};

function UpcomingPodiumCard({ driverId, position, probability }: { driverId: string; position: number; probability: number }) {
    const d = resolveDriver(driverId);
    const logo = d ? TEAM_LOGOS[d.team] : undefined;
    const style = UPCOMING_CARD_STYLES[position];

    return (
        <div className={`relative flex flex-col w-full md:w-[260px] rounded-xl overflow-hidden bg-[#111118] border border-white/10 ${style.order} ${style.scale} shadow-2xl`}>
            {/* Top right badge */}
            <div 
                className="absolute top-4 right-4 w-8 h-8 rounded-full flex items-center justify-center font-black text-black z-20 shadow-lg text-sm"
                style={{ backgroundColor: style.badgeColor }}
            >
                {style.badge}
            </div>

            {/* Background Glow & Large Shadow Text */}
            <div className="relative h-[240px] w-full flex items-end justify-center overflow-hidden bg-gradient-to-b from-transparent to-[#1a1a24]">
                <div 
                    className="absolute inset-0 mix-blend-screen pointer-events-none"
                    style={{ background: `radial-gradient(circle at center 60%, ${style.glow}44 0%, transparent 65%)` }}
                />
                <div className="absolute top-2 left-2 font-black italic text-[140px] leading-none opacity-5 pointer-events-none select-none -tracking-widest text-white">
                    P{position}
                </div>
                <div className="relative z-10 -mb-2 w-[75%] max-w-[190px]">
                    <DriverAvatar driverKey={driverId} size={240} />
                </div>
            </div>

            {/* Info Footer */}
            <div className="relative z-20 bg-[#1a1a24] p-5 text-center border-t border-white/5">
                <p className="text-[18px] font-black text-white italic tracking-wide uppercase leading-tight">
                    {d?.name ?? prettyName(driverId)}
                </p>
                <div className="flex items-center justify-center gap-2 mt-2">
                    {logo && <img src={logo} alt="" className="h-3 object-contain brightness-0 invert opacity-60" />}
                    <span className="text-[11px] text-white/50 uppercase tracking-[0.2em] font-bold">
                        {d?.team ?? "—"}
                    </span>
                </div>
                {probability > 0 && (
                    <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between px-2">
                        <span className="text-[10px] text-white/40 uppercase tracking-widest font-bold">Win Prob</span>
                        <span className="text-[13px] font-mono font-bold text-accent">
                            {(probability * 100).toFixed(1)}%
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
}
