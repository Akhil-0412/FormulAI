'use client';
import { CalendarCheck, MapPin, ChevronRight, Info } from "lucide-react";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Image from "next/image";

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

const CALENDAR = [
    { round: "TEST", name: "FORMULA 1 ARAMCO PRE-SEASON TESTING 1 2026", date: "11 - 13 Feb", location: "Bahrain", status: "Testing" },
    { round: "TEST", name: "FORMULA 1 ARAMCO PRE-SEASON TESTING 2 2026", date: "18 - 20 Feb", location: "Bahrain", status: "Testing" },
    { round: 1, name: "FORMULA 1 QATAR AIRWAYS AUSTRALIAN GRAND PRIX 2026", date: "06 - 08 Mar", location: "Australia", status: "Upcoming" },
    { round: 2, name: "FORMULA 1 HEINEKEN CHINESE GRAND PRIX 2026", date: "13 - 15 Mar", location: "China", status: "Upcoming" },
    { round: 3, name: "FORMULA 1 ARAMCO JAPANESE GRAND PRIX 2026", date: "27 - 29 Mar", location: "Japan", status: "Upcoming" },
    { round: 4, name: "FORMULA 1 GULF AIR BAHRAIN GRAND PRIX 2026", date: "10 - 12 Apr", location: "Bahrain", status: "Upcoming" },
    { round: 5, name: "FORMULA 1 STC SAUDI ARABIAN GRAND PRIX 2026", date: "17 - 19 Apr", location: "Saudi Arabia", status: "Upcoming" },
    { round: 6, name: "FORMULA 1 CRYPTO.COM MIAMI GRAND PRIX 2026", date: "01 - 03 May", location: "Miami", status: "Upcoming" },
    { round: 7, name: "FORMULA 1 LENOVO GRAND PRIX DU CANADA 2026", date: "22 - 24 May", location: "Canada", status: "Upcoming" },
    { round: 8, name: "FORMULA 1 LOUIS VUITTON GRAND PRIX DE MONACO 2026", date: "05 - 07 Jun", location: "Monaco", status: "Upcoming" },
    { round: 9, name: "FORMULA 1 MSC CRUISES GRAN PREMIO DE BARCELONA-CATALUNYA 2026", date: "12 - 14 Jun", location: "Barcelona-Catalunya", status: "Upcoming" },
    { round: 10, name: "FORMULA 1 LENOVO AUSTRIAN GRAND PRIX 2026", date: "26 - 28 Jun", location: "Austria", status: "Upcoming" },
    { round: 11, name: "FORMULA 1 PIRELLI BRITISH GRAND PRIX 2026", date: "03 - 05 Jul", location: "Great Britain", status: "Upcoming" },
    { round: 12, name: "FORMULA 1 MOËT & CHANDON BELGIAN GRAND PRIX 2026", date: "17 - 19 Jul", location: "Belgium", status: "Upcoming" },
    { round: 13, name: "FORMULA 1 AWS HUNGARIAN GRAND PRIX 2026", date: "24 - 26 Jul", location: "Hungary", status: "Upcoming" },
    { round: 14, name: "FORMULA 1 HEINEKEN DUTCH GRAND PRIX 2026", date: "21 - 23 Aug", location: "Netherlands", status: "Upcoming" },
    { round: 15, name: "FORMULA 1 PIRELLI GRAN PREMIO D’ITALIA 2026", date: "04 - 06 Sep", location: "Italy", status: "Upcoming" },
    { round: 16, name: "FORMULA 1 TAG HEUER GRAN PREMIO DE ESPAÑA 2026", date: "11 - 13 Sep", location: "Spain", status: "Upcoming" },
    { round: 17, name: "FORMULA 1 QATAR AIRWAYS AZERBAIJAN GRAND PRIX 2026", date: "24 - 26 Sep", location: "Azerbaijan", status: "Upcoming" },
    { round: 18, name: "FORMULA 1 SINGAPORE AIRLINES SINGAPORE GRAND PRIX 2026", date: "09 - 11 Oct", location: "Singapore", status: "Upcoming" },
    { round: 19, name: "FORMULA 1 MSC CRUISES UNITED STATES GRAND PRIX 2026", date: "23 - 25 Oct", location: "United States", status: "Upcoming" },
    { round: 20, name: "FORMULA 1 GRAN PREMIO DE LA CIUDAD DE MÉXICO 2026", date: "30 Oct - 01 Nov", location: "Mexico", status: "Upcoming" },
    { round: 21, name: "FORMULA 1 MSC CRUISES GRANDE PRÊMIO DE SÃO PAULO 2026", date: "06 - 08 Nov", location: "Brazil", status: "Upcoming" },
    { round: 22, name: "FORMULA 1 HEINEKEN LAS VEGAS GRAND PRIX 2026", date: "19 - 21 Nov", location: "Las Vegas", status: "Upcoming" },
    { round: 23, name: "FORMULA 1 QATAR AIRWAYS QATAR GRAND PRIX 2026", date: "27 - 29 Nov", location: "Qatar", status: "Upcoming" },
    { round: 24, name: "FORMULA 1 ETIHAD AIRWAYS ABU DHABI GRAND PRIX 2026", date: "04 - 06 Dec", location: "Abu Dhabi", status: "Upcoming" },
];

export default function SchedulePage() {
    const [notification, setNotification] = useState<string | null>(null);
    const [backtestData, setBacktestData] = useState<BacktestRace[]>([]);
    const [expandedRound, setExpandedRound] = useState<number | string | null>(null);

    useEffect(() => {
        fetch("/data/rolling_backtest_2026.json")
            .then(res => res.json())
            .then(data => setBacktestData(data))
            .catch(err => console.error("Could not load backtest data in schedule view", err));
    }, []);

    const handleRaceClick = (race: any) => {
        if (race.round === "TEST") {
            setNotification(`Data for ${race.name} is currently unavailable as it is a testing event.`);
            setTimeout(() => setNotification(null), 3000);
            return;
        }

        const raceData = backtestData.find(r => r.round === race.round);
        if (raceData) {
            setExpandedRound(expandedRound === race.round ? null : race.round);
        } else {
            setNotification(`Predictions for ${race.name} pending completion of prior races.`);
            setTimeout(() => setNotification(null), 3000);
        }
    };

    return (
        <div className="flex flex-col gap-10 max-w-7xl mx-auto mb-20 animate-in fade-in duration-700 relative">
            {/* Notification Toast */}
            <AnimatePresence>
                {notification && (
                    <motion.div
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        className="fixed top-24 left-1/2 transform -translate-x-1/2 z-50 glass-panel border border-f1-papaya/50 px-6 py-4 rounded-xl shadow-2xl flex items-center gap-3"
                    >
                        <Info className="text-f1-papaya w-5 h-5" />
                        <span className="text-white font-medium">{notification}</span>
                    </motion.div>
                )}
            </AnimatePresence>

            <div className="flex flex-col gap-2">
                <h1 className="text-4xl md:text-5xl font-black tracking-tight text-white italic tracking-tighter" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>
                    2026 Schedule
                </h1>
                <p className="text-f1-muted text-lg italic tracking-wider font-semibold" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>The official calendar for the upcoming season. Premium race views.</p>
            </div>

            <div className="flex flex-col gap-6">
                {CALENDAR.map((race, idx) => {
                    const raceData = typeof race.round === 'number' ? backtestData.find(r => r.round === race.round) : null;
                    const isExpanded = expandedRound === race.round;

                    return (
                    <div
                        key={`${race.round}-${idx}`}
                        className="group relative glass-panel rounded-3xl overflow-hidden border border-white/10 transition-all duration-500 shadow-lg flex flex-col"
                    >
                        {/* Background subtle gradient / glow on hover */}
                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/0 to-f1-teal/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />

                        <div 
                            onClick={() => handleRaceClick(race)}
                            className="relative z-10 p-6 md:p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-6 cursor-pointer hover:bg-white/5 transition-colors"
                        >
                            {/* Left Side: Date and Name */}
                            <div className="flex items-center gap-8">
                                {/* Round Number */}
                                <div className={`hidden md:flex flex-col items-center justify-center w-16 h-16 rounded-2xl bg-white/5 border border-white/10 ${race.status === 'Testing' ? 'group-hover:bg-f1-papaya' : 'group-hover:bg-f1-teal'} transition-colors duration-500`}>
                                    <span className="text-f1-muted text-xs font-bold uppercase tracking-widest group-hover:text-white/80 transition-colors">
                                        {race.status === 'Testing' ? 'TST' : 'Rnd'}
                                    </span>
                                    <span className="text-xl font-black text-white">{race.round}</span>
                                </div>

                                <div>
                                    <p className={`${race.status === 'Testing' ? 'text-f1-papaya' : 'text-f1-teal'} font-bold uppercase tracking-widest text-sm mb-1`}>{race.date}</p>
                                    <h2 className={`text-2xl md:text-3xl font-black ${raceData?.is_future ? 'text-f1-papaya' : 'text-white'} tracking-tight group-hover:scale-[1.01] transform transition-transform duration-500 origin-left leading-tight`}>
                                        {race.name}
                                    </h2>
                                    <div className="flex items-center gap-4 mt-2">
                                        <p className="flex items-center gap-1 text-f1-muted font-medium">
                                            <MapPin className="w-4 h-4 text-white/50" /> {race.location}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* Right Side: Status and Arrow */}
                            <div className="flex items-center gap-6 w-full md:w-auto mt-4 md:mt-0 pt-4 md:pt-0 border-t md:border-none border-white/10 justify-between md:justify-end">
                                <div className={`flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border ${raceData?.is_future ? 'border-f1-papaya' : 'border-white/10'} group-hover:bg-white/10 transition-colors`}>
                                    <div className={`w-2 h-2 rounded-full ${race.status === 'Testing' ? 'bg-f1-papaya' : (raceData?.is_future ? 'bg-f1-papaya' : 'bg-f1-teal')} animate-pulse`} />
                                    <span className={`${raceData?.is_future ? 'text-f1-papaya' : 'text-white'} font-semibold text-sm tracking-wide`}>
                                        {raceData ? (raceData.is_future ? 'Upcoming Prediction' : 'Completed') : race.status}
                                    </span>
                                </div>
                                <div className={`w-12 h-12 rounded-full bg-white/5 flex items-center justify-center text-white/50 group-hover:text-white group-hover:bg-white/10 transition-all duration-500 ${isExpanded ? 'rotate-90' : ''}`}>
                                    <ChevronRight className="w-6 h-6 transform transition-transform" />
                                </div>
                            </div>
                        </div>

                        {/* Expandable Prediction Section */}
                        <AnimatePresence>
                            {isExpanded && raceData && (
                                <motion.div
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: "auto", opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    transition={{ duration: 0.3, ease: "easeInOut" }}
                                    className="border-t border-white/10 bg-f1-navy/50 overflow-hidden"
                                >
                                    <div className="p-6 md:p-8 flex flex-col md:flex-row gap-8">
                                        {/* Predicted Podium */}
                                        <div className="flex-1 flex flex-col gap-3">
                                            <span className="text-xs font-bold text-f1-muted uppercase tracking-widest pl-2">ML Predicted Podium</span>
                                            {raceData.predicted.slice(0, 3).map((driverId, pidx) => {
                                                const dInfo = getDriverInfo(driverId);
                                                return (
                                                    <div key={`p-${pidx}`} className="flex items-center gap-4 bg-white/5 border border-white/5 rounded-xl p-2 relative overflow-hidden group hover:border-white/20 transition-colors">
                                                        <div className={`absolute top-0 left-0 bottom-0 w-1 ${pidx===0?'bg-f1-papaya':pidx===1?'bg-gray-400':'bg-amber-700'}`} />
                                                        <div className="w-8 font-black text-xl text-white/20 italic pl-2">P{pidx+1}</div>
                                                        <div className="w-10 h-10 rounded-full overflow-hidden relative bg-f1-navy">
                                                            {dInfo.img && <Image src={dInfo.img} alt={dInfo.name} fill className="object-cover object-top" unoptimized />}
                                                        </div>
                                                        <div className="flex flex-col">
                                                            <span className="text-white font-bold text-sm leading-tight">{dInfo.name}</span>
                                                            <span className="text-white/50 text-xs font-mono">{dInfo.team}</span>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>

                                        {/* Actual Podium */}
                                        <div className="flex-1 flex flex-col gap-3">
                                            <span className="text-xs font-bold text-f1-muted uppercase tracking-widest pl-2">Actual Podium</span>
                                            {raceData.is_future ? (
                                                <div className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-white/10 rounded-xl p-6 bg-white/5">
                                                    <span className="text-2xl font-black text-white/20 italic uppercase tracking-widest">TBA</span>
                                                    <span className="text-f1-muted text-sm mt-2">Waiting for Lights Out</span>
                                                </div>
                                            ) : (
                                                raceData.actual.slice(0, 3).map((driverId, pidx) => {
                                                    const dInfo = getDriverInfo(driverId);
                                                    return (
                                                        <div key={`a-${pidx}`} className="flex items-center gap-4 bg-white/5 border border-white/5 rounded-xl p-2 relative overflow-hidden group hover:border-white/20 transition-colors">
                                                            <div className={`absolute top-0 left-0 bottom-0 w-1 ${pidx===0?'bg-f1-papaya':pidx===1?'bg-gray-400':'bg-amber-700'}`} />
                                                            <div className="w-8 font-black text-xl text-white/20 italic pl-2">P{pidx+1}</div>
                                                            <div className="w-10 h-10 rounded-full overflow-hidden relative bg-f1-navy">
                                                                {dInfo.img && <Image src={dInfo.img} alt={dInfo.name} fill className="object-cover object-top" unoptimized />}
                                                            </div>
                                                            <div className="flex flex-col">
                                                                <span className="text-white font-bold text-sm leading-tight">{dInfo.name}</span>
                                                                <span className="text-white/50 text-xs font-mono">{dInfo.team}</span>
                                                            </div>
                                                        </div>
                                                    );
                                                })
                                            )}
                                        </div>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                )})}
            </div>
        </div>
    );
}
