"use client";

import { Search } from "lucide-react";
import AvatarCluster from "./ui/AvatarCluster";
import { DRIVERS } from "../constants/drivers";

/**
 * Top bar: wordmark, search, live grid status, session chip.
 *
 * The reference puts a roster summary ("10 of 12 on work") beside the
 * search. The F1 equivalent is the state of the grid, which is real
 * information rather than decoration.
 */

type Props = {
    driversOnGrid?: number;
    driversTotal?: number;
    teamCount?: number;
    apiConnected?: boolean;
};

export default function TopBar({
    driversOnGrid = 20,
    driversTotal = 20,
    teamCount = 10,
    apiConnected = true,
}: Props) {
    return (
        <header className="flex items-center gap-4 mb-6">
            {/* Wordmark */}
            <div className="flex items-baseline gap-[1px] select-none mr-2">
                <span className="text-[26px] font-bold tracking-[-0.04em] text-fg leading-none">
                    formul
                </span>
                <span className="text-[26px] font-bold tracking-[-0.04em] text-accent leading-none">
                    AI
                </span>
            </div>

            {/* Search */}
            <button
                aria-label="Search"
                className="w-10 h-10 shrink-0 rounded-full bg-ink-2 border border-line
                           grid place-items-center text-fg-muted hover:text-fg
                           hover:border-line-strong transition-colors"
            >
                <Search className="w-[17px] h-[17px]" strokeWidth={2} />
            </button>

            {/* Grid status */}
            <div className="hidden md:flex items-center gap-3 h-10 pl-2 pr-4 rounded-full
                            bg-ink-2 border border-line">
                <AvatarCluster
                    count={4}
                    overflow={driversTotal - 4}
                    srcs={DRIVERS.slice(0, 4).map((d) => d.img)}
                />
                <p className="text-[13px] text-fg whitespace-nowrap">
                    <span className="font-semibold num">
                        {driversOnGrid} of {driversTotal}
                    </span>
                    <span className="text-fg-muted"> on the grid</span>
                </p>
            </div>

            <div className="hidden lg:flex items-center h-10 px-4 rounded-full
                            bg-ink-2 border border-line">
                <p className="text-[13px] text-fg whitespace-nowrap">
                    <span className="font-semibold num">{teamCount}</span>
                    <span className="text-fg-muted"> teams</span>
                </p>
            </div>

            {/* Session */}
            <div className="ml-auto flex items-center gap-3">
                <div className="hidden sm:flex items-center gap-2 h-10 px-3.5 rounded-full
                                bg-ink-2 border border-line">
                    <span
                        className={apiConnected ? "live-dot" : "w-1.5 h-1.5 rounded-full bg-fg-subtle"}
                        style={apiConnected ? undefined : { animation: "none" }}
                    />
                    <span className="text-[11px] text-fg-muted tracking-wide">
                        {apiConnected ? "Live" : "Offline"}
                    </span>
                </div>

                <div className="text-right hidden sm:block leading-tight">
                    <p className="text-[13px] font-semibold text-fg">2026 Season</p>
                    <p className="text-[11px] text-accent">Intelligence Center</p>
                </div>
            </div>
        </header>
    );
}
