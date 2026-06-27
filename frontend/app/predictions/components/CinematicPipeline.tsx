"use client";

import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Gauge, Cpu, Database, Activity, Zap, TrendingUp, BarChart2, Layers } from "lucide-react";

export type PipelineStage = "idle" | "ingesting" | "processing" | "calibrating" | "complete";

interface Props {
    stage: PipelineStage;
}

const featuresGrouped = [
    {
        category: "Qualifying",
        icon: "⏱️",
        color: "from-blue-500 to-cyan-400",
        items: ["Grid Position", "Qualifying Gap to Pole", "Q3 Reached"]
    },
    {
        category: "Driver Form",
        icon: "🏎️",
        color: "from-red-500 to-orange-400",
        items: ["Driver Last 5 Avg Pos", "Driver Last 3 Avg Pos", "Podium Rate", "Recent DNF Rate"]
    },
    {
        category: "Circuit History",
        icon: "🏁",
        color: "from-amber-400 to-yellow-500",
        items: ["Circuit Avg Pos", "Circuit Best Pos", "Overtake Difficulty", "Circuit Type"]
    },
    {
        category: "Championship",
        icon: "🏆",
        color: "from-purple-500 to-pink-500",
        items: ["Championship Position", "Championship Points", "Constructor Reliability"]
    },
    {
        category: "Weather",
        icon: "🌤️",
        color: "from-emerald-400 to-teal-400",
        items: ["Temperature", "Precipitation Prob", "Wind Speed", "Humidity"]
    }
];

export default function CinematicPipeline({ stage }: Props) {
    const [progress, setProgress] = useState(0);

    // Fake progress simulation for the gauge
    useEffect(() => {
        if (stage === "idle" || stage === "complete") {
            setProgress(0);
            return;
        }

        let target = 0;
        if (stage === "ingesting") target = 30;
        if (stage === "processing") target = 75;
        if (stage === "calibrating") target = 99;

        const interval = setInterval(() => {
            setProgress(p => {
                const step = (target - p) * 0.1;
                return p + (step > 0.1 ? step : 0);
            });
        }, 50);

        return () => clearInterval(interval);
    }, [stage]);

    if (stage === "idle") return null;

    return (
        <AnimatePresence mode="wait">
            {stage !== "complete" && (
                <motion.div
                    key="pipeline"
                    initial={{ opacity: 0, height: 0, y: 20 }}
                    animate={{ opacity: 1, height: "auto", y: 0 }}
                    exit={{ opacity: 0, height: 0, y: -20 }}
                    transition={{ duration: 0.6, ease: "easeInOut" }}
                    className="w-full relative overflow-hidden rounded-3xl bg-black border border-white/10 shadow-[0_0_50px_rgba(220,38,38,0.15)]"
                >
                    {/* Background Grid & Glows */}
                    <div className="absolute inset-0 bg-[url('https://transparenttextures.com/patterns/cubes.png')] opacity-5 mix-blend-overlay"></div>
                    <div className="absolute -top-40 -right-40 w-96 h-96 bg-red-600/20 rounded-full blur-[100px]"></div>
                    <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-amber-600/20 rounded-full blur-[100px]"></div>

                    <div className="p-8 md:p-12 min-h-[400px] flex flex-col justify-between relative z-10">
                        {/* Header */}
                        <div className="flex justify-between items-start mb-8">
                            <div>
                                <h3 className="text-red-500 font-black tracking-[0.2em] uppercase text-xs mb-2 flex items-center gap-2">
                                    <Activity className="w-4 h-4 animate-pulse" />
                                    Prediction Engine Active
                                </h3>
                                <h2 className="text-3xl font-black text-white italic" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>
                                    {stage === "ingesting" && "Ingesting Features"}
                                    {stage === "processing" && "XGBoost LTR Processing"}
                                    {stage === "calibrating" && "Softmax Calibration"}
                                </h2>
                            </div>
                            <div className="text-right">
                                <div className="text-5xl font-mono font-black text-white">
                                    {Math.floor(progress)}<span className="text-red-500">%</span>
                                </div>
                            </div>
                        </div>

                        {/* Stage Content */}
                        <div className="relative flex-1 flex items-center justify-center min-h-[250px]">
                            <AnimatePresence mode="wait">
                                {stage === "ingesting" && <IngestingStage key="ingest" />}
                                {stage === "processing" && <ProcessingStage key="process" progress={progress} />}
                                {stage === "calibrating" && <CalibratingStage key="calibrate" />}
                            </AnimatePresence>
                        </div>

                        {/* Footer Status Bar */}
                        <div className="mt-8 flex items-center justify-between border-t border-white/10 pt-4">
                            <div className="flex gap-4">
                                <StatusDot label="Ingest" active={stage === "ingesting" || stage === "processing" || stage === "calibrating"} />
                                <StatusDot label="LambdaMART" active={stage === "processing" || stage === "calibrating"} />
                                <StatusDot label="Plackett-Luce" active={stage === "calibrating"} />
                            </div>
                            <div className="flex items-center gap-2 text-xs font-mono text-f1-muted">
                                <Cpu className="w-3 h-3" />
                                <span>Core: Optimal</span>
                            </div>
                        </div>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}

// ─── SUB-STAGES ─────────────────────────────────────────────────────────────

function IngestingStage() {
    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="w-full grid grid-cols-2 md:grid-cols-5 gap-4"
        >
            {featuresGrouped.map((group, i) => (
                <motion.div
                    key={group.category}
                    initial={{ y: 20, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: i * 0.15, duration: 0.5 }}
                    className="flex flex-col items-center text-center relative"
                >
                    <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-2xl mb-4 relative z-10 shadow-lg backdrop-blur-md">
                        {group.icon}
                        <motion.div
                            animate={{ opacity: [0, 1, 0] }}
                            transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.2 }}
                            className={`absolute inset-0 rounded-2xl bg-gradient-to-br ${group.color} opacity-20 blur-md -z-10`}
                        />
                    </div>
                    <h4 className="text-xs font-bold text-white mb-2 uppercase tracking-wider">{group.category}</h4>
                    <div className="flex flex-col gap-1 w-full">
                        {group.items.map((item, j) => (
                            <motion.div
                                key={item}
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: i * 0.15 + j * 0.1 + 0.3 }}
                                className="text-[9px] text-f1-muted bg-white/5 py-1 px-2 rounded font-mono truncate"
                            >
                                {item}
                            </motion.div>
                        ))}
                    </div>
                </motion.div>
            ))}
        </motion.div>
    );
}

function ProcessingStage({ progress }: { progress: number }) {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.1 }}
            className="w-full flex items-center justify-center gap-12"
        >
            {/* Left Data Stream */}
            <div className="hidden md:flex flex-col gap-2 font-mono text-[10px] text-red-500/50 text-right">
                {Array.from({ length: 8 }).map((_, i) => (
                    <motion.div
                        key={`l-${i}`}
                        animate={{ opacity: [0.2, 1, 0.2] }}
                        transition={{ duration: 0.5 + Math.random(), repeat: Infinity }}
                    >
                        0x{(Math.random() * 0xfffff).toString(16).padStart(5, '0')}
                    </motion.div>
                ))}
            </div>

            {/* Central RPM Gauge */}
            <div className="relative w-48 h-48 md:w-64 md:h-64 flex items-center justify-center">
                <svg className="w-full h-full -rotate-90 drop-shadow-[0_0_15px_rgba(239,68,68,0.5)]">
                    {/* Track */}
                    <circle cx="50%" cy="50%" r="45%" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
                    {/* Progress */}
                    <motion.circle
                        cx="50%" cy="50%" r="45%" fill="none"
                        stroke="url(#gradient)" strokeWidth="8" strokeLinecap="round"
                        strokeDasharray="283%"
                        animate={{ strokeDashoffset: `${283 - (283 * progress) / 100}%` }}
                        transition={{ ease: "linear", duration: 0.1 }}
                    />
                    <defs>
                        <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" stopColor="#ef4444" />
                            <stop offset="50%" stopColor="#f59e0b" />
                            <stop offset="100%" stopColor="#3b82f6" />
                        </linearGradient>
                    </defs>
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <Database className="w-8 h-8 text-white/50 mb-2" />
                    <span className="text-2xl font-black text-white">{Math.floor(progress * 14.3)}</span>
                    <span className="text-[10px] text-red-400 uppercase tracking-widest mt-1">Trees/Sec</span>
                </div>
            </div>

            {/* Right Data Stream */}
            <div className="hidden md:flex flex-col gap-2 font-mono text-[10px] text-amber-500/50 text-left">
                {Array.from({ length: 8 }).map((_, i) => (
                    <motion.div
                        key={`r-${i}`}
                        animate={{ opacity: [0.2, 1, 0.2] }}
                        transition={{ duration: 0.5 + Math.random(), repeat: Infinity }}
                    >
                        ndcg_{(Math.random()).toFixed(4)}
                    </motion.div>
                ))}
            </div>
        </motion.div>
    );
}

function CalibratingStage() {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="w-full max-w-2xl flex flex-col gap-3"
        >
            {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4">
                    <div className="w-16 text-right font-mono text-xs text-white/50">Driver {i + 1}</div>
                    <div className="flex-1 h-3 bg-white/5 rounded-full overflow-hidden relative">
                        <motion.div
                            initial={{ width: "0%" }}
                            animate={{ width: `${80 - i * 15 + Math.random() * 10}%` }}
                            transition={{ duration: 1, delay: i * 0.1, type: "spring", stiffness: 50 }}
                            className={`h-full rounded-full ${
                                i === 0 ? "bg-gradient-to-r from-yellow-600 to-yellow-400" :
                                i === 1 ? "bg-gradient-to-r from-gray-500 to-gray-300" :
                                i === 2 ? "bg-gradient-to-r from-amber-700 to-amber-500" :
                                "bg-gradient-to-r from-blue-600 to-blue-400"
                            }`}
                        />
                    </div>
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 1 + i * 0.1 }}
                        className="w-12 text-left font-mono text-xs font-bold text-white"
                    >
                        {(Math.random() * 0.5 + 0.1).toFixed(3)}
                    </motion.div>
                </div>
            ))}
        </motion.div>
    );
}

function StatusDot({ label, active }: { label: string, active: boolean }) {
    return (
        <div className={`flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider transition-colors duration-300 ${active ? 'text-white' : 'text-white/20'}`}>
            <div className={`w-2 h-2 rounded-full ${active ? 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.8)]' : 'bg-white/10'}`} />
            {label}
        </div>
    );
}
