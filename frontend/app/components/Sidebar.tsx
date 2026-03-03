"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Calendar, Trophy, Map, Users, BrainCircuit, Bot } from "lucide-react";
import { motion } from "framer-motion";

const navItems = [
    { name: "Home", href: "/", icon: Home },
    { name: "Schedule", href: "/schedule", icon: Calendar },
    { name: "Results", href: "/results", icon: Trophy },
    { name: "Standings", href: "/standings", icon: Users },
    { name: "Tracks", href: "/tracks", icon: Map },
    { name: "Teams", href: "/teams", icon: Users },
    { name: "Predictions", href: "/predictions", icon: BrainCircuit },
    { name: "ParcFermé AI", href: "/parcferme", icon: Bot },
];

export default function Sidebar() {
    const pathname = usePathname();

    return (
        <div className="w-64 h-screen fixed top-0 left-0 border-r border-f1-border bg-f1-dark/95 backdrop-blur-3xl flex flex-col p-6 z-50">
            <div className="flex items-center gap-3 mb-12 ml-1">
                <div className="relative w-full max-w-[140px] h-14 rounded-[14px] shadow-[0_0_30px_10px_rgba(232,0,32,0.4)] bg-f1-dark shrink-0 flex items-center justify-center p-1">
                    <img src="/assets/AppLogo.png" alt="ParcFermé AI Logo" className="w-full h-full object-contain rounded-[10px]" />
                </div>
            </div>

            <nav className="flex flex-col gap-2">
                <h3 className="text-xs font-semibold text-f1-muted uppercase tracking-wider mb-2 ml-3">Navigation</h3>
                {navItems.map((item) => {
                    const isActive = pathname === item.href;
                    const Icon = item.icon;
                    const isAi = item.name === "Predictions" || item.name === "ParcFermé AI";

                    return (
                        <Link
                            key={item.name}
                            href={item.href}
                            className={`relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group ${isActive ? "text-white" : "text-f1-muted hover:text-white"
                                } ${isAi ? "gold-glowing-tab my-0.5 shadow-lg shadow-amber-500/10" : ""}`}
                        >
                            {isActive && (
                                <motion.div
                                    layoutId="active-nav"
                                    className="absolute inset-0 bg-white/10 rounded-xl z-[1]"
                                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                                />
                            )}
                            <Icon className={`w-5 h-5 relative z-10 ${isActive ? "text-f1-red" : isAi ? "text-amber-400" : "text-f1-muted group-hover:text-white"}`} />
                            <span className={`relative z-10 ${isAi ? "text-amber-300 font-bold tracking-wide drop-shadow-md" : ""}`}>{item.name}</span>
                        </Link>
                    );
                })}
            </nav>

            <div className="mt-auto">
                <div className="glass-panel rounded-xl p-4 text-center">
                    <div className="w-2 h-2 rounded-full bg-emerald-500 mx-auto mb-2 animate-pulse" />
                    <p className="text-xs text-f1-muted font-medium">API Connected</p>
                </div>
            </div>
        </div>
    );
}
