"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
    Home, Calendar, Trophy, Map, Users, BrainCircuit, Bot
} from "lucide-react";
import { motion } from "framer-motion";
import GlassSurface from "./ui/GlassSurface";

/**
 * Floating navigation dock — bottom centre, landscape.
 *
 * At rest it recedes: shrunk slightly and tucked a touch above its full
 * position, so it keeps a presence without competing with the page.
 * Pointer contact or keyboard focus brings it back to full size
 * immediately; leaving holds it open for a beat (so a quick pass between
 * icons doesn't retrigger the shrink) before it recedes again.
 *
 * GlassSurface adds a genuine SVG-refraction pass on top of the usual
 * backdrop-blur, giving the dock a thick-glass read rather than a flat
 * translucent panel. Falls back to heavier blur on browsers that don't
 * support url() inside backdrop-filter.
 */

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

/** How long the dock stays full-size after the pointer/focus leaves it. */
const COLLAPSE_DELAY_MS = 3000;
/** How long it stays open on first load before settling, so it isn't
    shrunk the instant the page appears. */
const INITIAL_SETTLE_MS = 3000;

export default function Dock() {
    const pathname = usePathname();
    const [expanded, setExpanded] = useState(true);
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

    const clearPending = () => {
        if (timer.current) {
            clearTimeout(timer.current);
            timer.current = null;
        }
    };

    const scheduleCollapse = (delay: number) => {
        clearPending();
        timer.current = setTimeout(() => setExpanded(false), delay);
    };

    // Settle to the compact resting state a few seconds after mount,
    // unless the pointer's already there.
    useEffect(() => {
        scheduleCollapse(INITIAL_SETTLE_MS);
        return clearPending;
    }, []);

    const handleEnter = () => {
        clearPending();
        setExpanded(true);
    };

    const handleLeave = () => {
        scheduleCollapse(COLLAPSE_DELAY_MS);
    };

    return (
        <nav
            aria-label="Primary"
            data-expanded={expanded}
            onPointerEnter={handleEnter}
            onPointerLeave={handleLeave}
            onFocus={handleEnter}
            onBlur={(e) => {
                // Moving focus between icons inside the dock shouldn't
                // trigger the collapse timer — only leaving it entirely.
                if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                    handleLeave();
                }
            }}
            className="dock fixed bottom-4 left-1/2 z-50
                       flex items-center gap-1 px-2 py-2
                       rounded-[20px]
                       shadow-[0_10px_40px_rgba(0,0,0,0.55),0_0_0_1px_rgba(255,255,255,0.08)]
                       max-w-[calc(100vw-2rem)] overflow-x-auto no-scrollbar"
        >
            {/* Fluid glass surface — refraction + specular. Must be first child. */}
            <GlassSurface />

            {/* Nav content sits above the glass layer */}
            <div className="relative z-10 flex items-center gap-1">
                {navItems.map((item) => {
                    const isActive = pathname === item.href;
                    const Icon = item.icon;

                    return (
                        <Link
                            key={item.name}
                            href={item.href}
                            aria-label={item.name}
                            aria-current={isActive ? "page" : undefined}
                            className="relative group w-11 h-11 rounded-[14px] grid place-items-center shrink-0"
                        >
                            {isActive && (
                                <motion.span
                                    layoutId="dock-active"
                                    className="absolute inset-0 rounded-[14px] bg-accent-wash border border-accent/45"
                                    transition={{ type: "spring", stiffness: 380, damping: 32 }}
                                />
                            )}
                            <Icon
                                className={`w-[18px] h-[18px] relative z-10 transition-colors ${isActive ? "text-accent" : "text-fg-muted group-hover:text-fg"
                                    }`}
                                strokeWidth={1.9}
                            />

                            {/* Label tooltip surfaces above the dock */}
                            <span
                                role="tooltip"
                                className="pointer-events-none absolute bottom-[calc(100%+10px)] left-1/2 -translate-x-1/2
                                           whitespace-nowrap rounded-lg bg-ink-4 border border-line
                                           px-2.5 py-1.5 text-xs text-fg opacity-0
                                           group-hover:opacity-100 group-focus-visible:opacity-100
                                           transition-opacity z-50"
                            >
                                {item.name}
                            </span>
                        </Link>
                    );
                })}
            </div>
        </nav>
    );
}
