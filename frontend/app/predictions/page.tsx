"use client";

import { useState, useEffect } from "react";
import {
    BrainCircuit, TrendingUp, Thermometer, Droplets, Wind, CloudRain,
    CheckCircle2, XCircle, AlertTriangle, ChevronDown, ChevronUp,
    Zap, Target, Gauge, Shield, Timer, MapPin, Flag
} from "lucide-react";
import Image from "next/image";

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
}

/* ═══════════════════════════════════════════════════════════════════════
   DRIVER / TEAM DATA
   ═══════════════════════════════════════════════════════════════════════ */

const TEAM_LOGOS: Record<string, string> = {
    "Red Bull Racing": "/assets/Teams/Red Bull Racing/2025redbullracinglogowhite.avif",
    "McLaren": "/assets/Teams/McLaren/2025mclarenlogowhite.avif",
    "Ferrari": "/assets/Teams/Ferrari/2025ferrarilogolight.avif",
    "Mercedes": "/assets/Teams/Mercedes/2025mercedeslogowhite.avif",
    "Aston Martin": "/assets/Teams/Aston Martin/astonmartinlogo.avif",
    "Alpine": "/assets/Teams/Alpine/alpinelogo.avif",
    "Williams": "/assets/Teams/Williams/williamslogo.avif",
    "Haas": "/assets/Teams/Haas F1 Team/2025haaslogowhite.avif",
    "RB": "/assets/Teams/Racing Bulls/2025racingbullslogowhite.avif",
    "Audi": "/assets/Teams/Audi/2026audilogowhite.avif",
    "Cadillac": "/assets/Teams/Cadillac/2026cadillaclogowhite.avif",
};

const CONSTRUCTOR_TO_TEAM: Record<string, string> = {
    red_bull: "Red Bull Racing", mclaren: "McLaren", ferrari: "Ferrari",
    mercedes: "Mercedes", aston_martin: "Aston Martin", alpine: "Alpine",
    williams: "Williams", haas: "Haas", rb: "RB", sauber: "Audi",
    cadillac: "Cadillac", alphatauri: "RB",
};

const DRIVER_DATA: Record<string, { name: string; team: string; img: string }> = {
    max_verstappen: { name: "Max Verstappen", team: "Red Bull Racing", img: "/assets/Teams/Red Bull Racing/2025redbullracingmaxver01right.avif" },
    norris: { name: "Lando Norris", team: "McLaren", img: "/assets/Teams/McLaren/2025mclarenlannor01right.avif" },
    piastri: { name: "Oscar Piastri", team: "McLaren", img: "/assets/Teams/McLaren/2025mclarenoscpia01right.avif" },
    leclerc: { name: "Charles Leclerc", team: "Ferrari", img: "/assets/Teams/Ferrari/2025ferrarichalec01right.avif" },
    hamilton: { name: "Lewis Hamilton", team: "Ferrari", img: "/assets/Teams/Ferrari/2025ferrarilewham01right.avif" },
    russell: { name: "George Russell", team: "Mercedes", img: "/assets/Teams/Mercedes/2025mercedesgeorus01right.avif" },
    antonelli: { name: "Kimi Antonelli", team: "Mercedes", img: "/assets/Teams/Mercedes/2025mercedesandant01right.avif" },
    alonso: { name: "Fernando Alonso", team: "Aston Martin", img: "/assets/Teams/Aston Martin/astonmartinferalo.avif" },
    stroll: { name: "Lance Stroll", team: "Aston Martin", img: "/assets/Teams/Aston Martin/astonmartinlanstr.avif" },
    gasly: { name: "Pierre Gasly", team: "Alpine", img: "/assets/Teams/Alpine/alpinepiegas.avif" },
    doohan: { name: "Franco Colapinto", team: "Alpine", img: "/assets/Teams/Alpine/alpinefracol.avif" },
    albon: { name: "Alex Albon", team: "Williams", img: "/assets/Teams/Williams/williamsalealb.avif" },
    sainz: { name: "Carlos Sainz", team: "Williams", img: "/assets/Teams/Williams/williamscarsai.avif" },
    ocon: { name: "Esteban Ocon", team: "Haas", img: "/assets/Teams/Haas F1 Team/2025haasestoco01right.avif" },
    bearman: { name: "Oliver Bearman", team: "Haas", img: "/assets/Teams/Haas F1 Team/2025haasolibea01right.avif" },
    tsunoda: { name: "Arvid Lindblad", team: "RB", img: "/assets/Teams/Racing Bulls/2026racingbullsarvlin01right.avif" },
    hadjar: { name: "Isack Hadjar", team: "Red Bull Racing", img: "/assets/Teams/Red Bull Racing/2026redbullracingisahad01right.avif" },
    lawson: { name: "Liam Lawson", team: "RB", img: "/assets/Teams/Racing Bulls/2025racingbullslialaw01right.avif" },
    hulkenberg: { name: "Nico Hulkenberg", team: "Audi", img: "/assets/Teams/Audi/2026audinichul01right.avif" },
    bortoleto: { name: "Gabriel Bortoleto", team: "Audi", img: "/assets/Teams/Audi/2026audigabbor01right.avif" },
};

const getDriverInfo = (id: string) => DRIVER_DATA[id] || { name: id.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()), team: "Unknown", img: "" };
const getTeamFromConstructor = (cid: string) => CONSTRUCTOR_TO_TEAM[cid] || cid.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());

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

export default function PredictionsPage() {
    const [backtestData, setBacktestData] = useState<BacktestRace[]>([]);
    const [fullRace, setFullRace] = useState<FullRaceResponse | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [progress, setProgress] = useState(0);
    const [showFullGrid, setShowFullGrid] = useState(false);
    const [showParams, setShowParams] = useState(false);

    useEffect(() => {
        fetch("/data/rolling_backtest_2025.json")
            .then(res => res.json())
            .then(data => setBacktestData(data))
            .catch(err => console.error("Backtest load failed:", err));
    }, []);

    const runPrediction = async () => {
        setIsLoading(true);
        setProgress(0);
        setFullRace(null);
        setShowFullGrid(false);

        const interval = setInterval(() => {
            setProgress(p => (p >= 92 ? 92 : p + Math.random() * 6));
        }, 150);

        try {
            // Using 2025 R1 as proxy for 2026 R1 Australia
            const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const res = await fetch(`${baseUrl}/api/v1/predict/2025/1/full-race`);
            const data: FullRaceResponse = await res.json();

            clearInterval(interval);
            setProgress(100);

            setTimeout(() => {
                setFullRace(data);
                setIsLoading(false);
            }, 600);
        } catch (error) {
            console.error("Full race prediction failed:", error);
            clearInterval(interval);
            setIsLoading(false);
        }
    };

    // Backtest aggregate stats
    const totalCorrect = backtestData.reduce((s, r) => s + r.correct, 0);
    const totalPossible = backtestData.length * 3;
    const overallAccuracy = totalPossible > 0 ? ((totalCorrect / totalPossible) * 100).toFixed(1) : "0";
    const perfectRaces = backtestData.filter(r => r.correct === 3).length;
    const avgBrier = backtestData.length > 0
        ? (backtestData.reduce((s, r) => s + r.brier_score, 0) / backtestData.length).toFixed(4) : "0";

    const formatDriverId = (id: string) => {
        if (!id) return "---";
        if (id === "max_verstappen") return "VER";
        return id.substring(0, 3).toUpperCase();
    };

    return (
        <div className="flex flex-col gap-10 max-w-7xl mx-auto mb-20 animate-in fade-in duration-700 w-full">
            <div className="flex flex-col gap-2">
                <h1 className="text-4xl md:text-5xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-500 italic" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>
                    Intelligence Center
                </h1>
                <p className="text-f1-muted text-lg italic tracking-wider font-semibold" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>
                    Predictive modeling using historical telemetry and Monte Carlo simulations.
                </p>
            </div>

            {/* ═════════════════════════════════════════════════════════════
               2026 RACE DAY PREDICTION
               ═════════════════════════════════════════════════════════════ */}
            <section className="flex flex-col gap-6">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <h2 className="text-3xl font-black text-white italic flex items-center gap-3">
                            <Flag className="w-7 h-7 text-red-500" />
                            2026 Australia Grand Prix — Race Prediction
                        </h2>
                        <p className="text-f1-muted text-sm mt-1">Albert Park Street Circuit · Melbourne, Australia · March 2026</p>
                    </div>
                    <button
                        onClick={runPrediction}
                        disabled={isLoading}
                        className={`px-8 py-4 rounded-xl font-black text-lg transition-all shadow-lg whitespace-nowrap ${isLoading
                            ? "bg-white/10 cursor-not-allowed text-white/50"
                            : "bg-gradient-to-r from-red-600 to-orange-500 hover:from-red-500 hover:to-orange-400 text-white shadow-red-500/30 hover:shadow-red-500/50 hover:scale-105"
                            }`}
                    >
                        {isLoading ? "🔄 Computing..." : "🏁 Run Prediction"}
                    </button>
                </div>

                {/* Loading Bar */}
                {isLoading && (
                    <div className="w-full bg-white/5 rounded-full h-3 overflow-hidden">
                        <div className="bg-gradient-to-r from-red-500 via-orange-400 to-yellow-400 h-full transition-all duration-150 rounded-full" style={{ width: `${progress}%` }} />
                    </div>
                )}

                {/* ── RESULTS ───────────────────────────────────────────── */}
                {fullRace && (
                    <div className="flex flex-col gap-8 animate-in fade-in slide-in-from-bottom-4 duration-700">

                        {/* ── Weather & Circuit ───────────────────────── */}
                        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                            <WeatherCard icon={<Thermometer className="w-5 h-5" />} label="Temperature" value={fullRace.weather.temperature != null ? `${fullRace.weather.temperature}°C` : "N/A"} />
                            <WeatherCard icon={<CloudRain className="w-5 h-5" />} label="Rain Chance" value={fullRace.weather.precipitation_prob != null ? `${fullRace.weather.precipitation_prob}%` : "N/A"} highlight={fullRace.weather.precipitation_prob != null && fullRace.weather.precipitation_prob > 40} />
                            <WeatherCard icon={<Wind className="w-5 h-5" />} label="Wind Speed" value={fullRace.weather.wind_speed != null ? `${fullRace.weather.wind_speed} km/h` : "N/A"} />
                            <WeatherCard icon={<Droplets className="w-5 h-5" />} label="Humidity" value={fullRace.weather.humidity != null ? `${fullRace.weather.humidity}%` : "N/A"} />
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

                        {/* ── PODIUM REVEAL ───────────────────────────── */}
                        <div className="relative">
                            <div className="absolute inset-0 bg-gradient-to-b from-purple-600/10 to-transparent rounded-3xl" />
                            <div className="glass-card p-8 relative overflow-hidden">
                                <h3 className="text-xs font-bold text-f1-muted uppercase tracking-[0.3em] mb-8 text-center">
                                    Predicted Podium — 2026 Australia Grand Prix
                                </h3>

                                <div className="flex flex-col md:flex-row items-end justify-center gap-4 md:gap-6">
                                    {/* P2 */}
                                    {fullRace.podium[1] && <PodiumCard driverId={fullRace.podium[1]} position={2} grid={fullRace.full_grid} constructorId={fullRace.full_grid.find(d => d.driver_id === fullRace.podium[1])?.constructor_id || ""} />}
                                    {/* P1 */}
                                    {fullRace.podium[0] && <PodiumCard driverId={fullRace.podium[0]} position={1} grid={fullRace.full_grid} constructorId={fullRace.full_grid.find(d => d.driver_id === fullRace.podium[0])?.constructor_id || ""} />}
                                    {/* P3 */}
                                    {fullRace.podium[2] && <PodiumCard driverId={fullRace.podium[2]} position={3} grid={fullRace.full_grid} constructorId={fullRace.full_grid.find(d => d.driver_id === fullRace.podium[2])?.constructor_id || ""} />}
                                </div>
                            </div>
                        </div>

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
                                        const drv = getDriverInfo(driver.driver_id);
                                        const teamName = drv.team !== "Unknown" ? drv.team : getTeamFromConstructor(driver.constructor_id);
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
                                                <div className="relative w-12 h-12 rounded-full overflow-hidden border-2 border-white/20 flex-shrink-0">
                                                    {drv.img ? (
                                                        <img src={drv.img} alt={drv.name} className="w-full h-full object-cover object-top" />
                                                    ) : (
                                                        <div className="w-full h-full bg-white/10 flex items-center justify-center text-xl">👤</div>
                                                    )}
                                                </div>

                                                {/* Name + Team */}
                                                <div className="flex flex-col flex-1 min-w-0">
                                                    <span className="font-bold text-white text-sm truncate">{drv.name}</span>
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
            </section>

            {/* ═════════════════════════════════════════════════════════════
               MODEL VALIDATION — 2025 Backtest
               ═════════════════════════════════════════════════════════════ */}
            <section className="flex flex-col gap-6 pt-8 border-t border-white/10">
                <div className="flex items-center gap-3">
                    <TrendingUp className="w-6 h-6 text-emerald-400" />
                    <h2 className="text-2xl font-bold text-white">Model Validation — 2025 Season (Unseen Data)</h2>
                </div>
                <p className="text-f1-muted text-sm -mt-4">
                    Trained on 2018–2024 · Rolling retrain after each race · Predicting the 2025 season the model has never seen
                </p>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="glass-panel rounded-2xl p-4 text-center">
                        <p className="text-xs text-f1-muted uppercase tracking-wider mb-1">Overall Accuracy</p>
                        <p className="text-3xl font-black text-emerald-400 font-mono">{overallAccuracy}%</p>
                    </div>
                    <div className="glass-panel rounded-2xl p-4 text-center">
                        <p className="text-xs text-f1-muted uppercase tracking-wider mb-1">Perfect Podiums</p>
                        <p className="text-3xl font-black text-amber-400 font-mono">{perfectRaces}</p>
                    </div>
                    <div className="glass-panel rounded-2xl p-4 text-center">
                        <p className="text-xs text-f1-muted uppercase tracking-wider mb-1">Avg Brier Score</p>
                        <p className="text-3xl font-black text-blue-400 font-mono">{avgBrier}</p>
                    </div>
                    <div className="glass-panel rounded-2xl p-4 text-center">
                        <p className="text-xs text-f1-muted uppercase tracking-wider mb-1">Races Evaluated</p>
                        <p className="text-3xl font-black text-white font-mono">{backtestData.length}</p>
                    </div>
                </div>

                {/* Backtest race-by-race with VS layout */}
                <div className="flex flex-col gap-8 mt-2">
                    {backtestData.map((race) => (
                        <div key={race.round} className="flex flex-col gap-4 relative">
                            <div className="flex justify-between items-center border-b border-white/10 pb-2">
                                <h3 className="text-xl font-black text-white italic">{race.race_name}</h3>
                                <div className={`px-3 py-1 rounded-full text-xs font-bold ${race.correct === 3 ? 'bg-emerald-500/20 text-emerald-400' : race.correct >= 2 ? 'bg-amber-500/20 text-amber-400' : race.correct >= 1 ? 'bg-blue-500/20 text-blue-400' : 'bg-red-500/20 text-red-400'}`}>
                                    {race.correct}/3 Correct · Brier: {race.brier_score.toFixed(3)}
                                </div>
                            </div>
                            <div className="grid grid-cols-[1fr_auto_1fr] gap-4 items-center w-full">
                                <div className="flex flex-col gap-3">
                                    <h4 className="text-xs text-f1-muted uppercase tracking-widest text-center font-bold mb-2">Predicted Podium</h4>
                                    {race.predicted.map((driverId, idx) => {
                                        const drv = getDriverInfo(driverId);
                                        const isCorrect = race.actual.includes(driverId);
                                        const prob = race.probabilities?.[driverId] || 0;
                                        const logo = TEAM_LOGOS[drv.team];
                                        return (
                                            <div key={idx} className={`flex items-center gap-3 p-3 rounded-lg border transition-all ${isCorrect ? "bg-emerald-900/30 shadow-[0_0_20px_rgba(16,185,129,0.2)] border-emerald-500/40" : "bg-red-900/30 shadow-[0_0_20px_rgba(239,68,68,0.3)] border-red-500/40"}`}>
                                                <div className="text-sm font-black text-white/50 w-6 text-center">P{idx + 1}</div>
                                                <div className={`relative w-12 h-12 rounded-full overflow-hidden border-2 ${isCorrect ? 'border-emerald-400' : 'border-red-500 grayscale'}`}>
                                                    {drv.img ? <img src={drv.img} alt={drv.name} className="w-full h-full object-cover object-top" /> : <div className="w-full h-full bg-white/10 flex items-center justify-center text-xl">👤</div>}
                                                </div>
                                                <div className="flex flex-col flex-1 min-w-0">
                                                    <span className="font-bold text-white truncate text-sm">{drv.name}</span>
                                                    <div className="flex gap-2 items-center">
                                                        {logo && <img src={logo} className="h-3 object-contain brightness-0 invert opacity-60" alt={drv.team} />}
                                                        <span className="text-[10px] text-f1-muted uppercase tracking-wider truncate">{drv.team}</span>
                                                    </div>
                                                </div>
                                                {prob > 0 && <span className={`text-base font-mono font-bold ${isCorrect ? 'text-emerald-400' : 'text-red-400'}`}>{(prob * 100).toFixed(1)}%</span>}
                                            </div>
                                        );
                                    })}
                                </div>
                                <div className="text-2xl font-black italic text-white/20 px-4 pt-10" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>VS</div>
                                <div className="flex flex-col gap-3">
                                    <h4 className="text-xs text-f1-muted uppercase tracking-widest text-center font-bold mb-2">Actual Podium</h4>
                                    {race.actual.map((driverId, idx) => {
                                        const drv = getDriverInfo(driverId);
                                        const logo = TEAM_LOGOS[drv.team];
                                        return (
                                            <div key={idx} className="flex items-center gap-3 p-3 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 transition-colors">
                                                <div className="text-sm font-black text-white/80 w-6 text-center">P{idx + 1}</div>
                                                <div className="relative w-12 h-12 rounded-full overflow-hidden border-2 border-white/20">
                                                    {drv.img ? <img src={drv.img} alt={drv.name} className="w-full h-full object-cover object-top" /> : <div className="w-full h-full bg-white/10 flex items-center justify-center text-xl">👤</div>}
                                                </div>
                                                <div className="flex flex-col flex-1 min-w-0">
                                                    <span className="font-bold text-white truncate text-sm">{drv.name}</span>
                                                    <div className="flex gap-2 items-center">
                                                        {logo && <img src={logo} className="h-3 object-contain brightness-0 invert opacity-60" alt={drv.team} />}
                                                        <span className="text-[10px] text-f1-muted uppercase tracking-wider truncate">{drv.team}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </section>
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
    const drv = getDriverInfo(driverId);
    const teamName = drv.team !== "Unknown" ? drv.team : getTeamFromConstructor(constructorId);
    const logo = TEAM_LOGOS[teamName];
    const gridEntry = grid.find(g => g.driver_id === driverId);

    const heights: Record<number, string> = { 1: "md:order-2 md:pb-0", 2: "md:order-1 md:pt-8", 3: "md:order-3 md:pt-12" };
    const sizes: Record<number, string> = { 1: "w-28 h-28 md:w-36 md:h-36", 2: "w-24 h-24 md:w-28 md:h-28", 3: "w-20 h-20 md:w-24 md:h-24" };
    const medals: Record<number, string> = { 1: "🥇", 2: "🥈", 3: "🥉" };
    const borders: Record<number, string> = { 1: "border-yellow-400 shadow-yellow-400/30", 2: "border-gray-300 shadow-gray-300/20", 3: "border-amber-600 shadow-amber-600/20" };

    return (
        <div className={`flex flex-col items-center gap-3 ${heights[position]}`}>
            <div className="text-4xl">{medals[position]}</div>
            <div className={`relative ${sizes[position]} rounded-full overflow-hidden border-4 shadow-lg ${borders[position]}`}>
                {drv.img ? (
                    <img src={drv.img} alt={drv.name} className="w-full h-full object-cover object-top" />
                ) : (
                    <div className="w-full h-full bg-white/10 flex items-center justify-center text-3xl">👤</div>
                )}
            </div>
            <div className="text-center">
                <p className="text-lg font-black text-white">{drv.name}</p>
                <div className="flex items-center justify-center gap-2 mt-1">
                    {logo && <img src={logo} className="h-4 object-contain brightness-0 invert opacity-70" alt={teamName} />}
                    <span className="text-xs text-f1-muted uppercase tracking-wider">{teamName}</span>
                </div>
            </div>
            <div className="flex gap-3 mt-1">
                <div className="text-center">
                    <span className="text-xs text-f1-muted">P{position} Prob</span>
                    <p className="text-lg font-black text-emerald-400 font-mono">
                        {gridEntry ? `${(position === 1 ? gridEntry.p1_probability : position === 2 ? gridEntry.p2_probability : gridEntry.p3_probability) * 100}`.substring(0, 4) + "%" : "—"}
                    </p>
                </div>
                <div className="text-center">
                    <span className="text-xs text-f1-muted">DNF Risk</span>
                    <p className={`text-lg font-black font-mono ${gridEntry && gridEntry.dnf_risk > 0.1 ? "text-amber-400" : "text-emerald-400"}`}>
                        {gridEntry ? `${(gridEntry.dnf_risk * 100).toFixed(0)}%` : "—"}
                    </p>
                </div>
            </div>
            {gridEntry?.expected_lap_time_sec && (
                <div className="text-center">
                    <span className="text-[10px] text-f1-muted">Est. Lap Time</span>
                    <p className="text-sm font-mono text-white/80">
                        {Math.floor(gridEntry.expected_lap_time_sec / 60)}:{(gridEntry.expected_lap_time_sec % 60).toFixed(3).padStart(6, "0")}
                    </p>
                </div>
            )}
        </div>
    );
}
