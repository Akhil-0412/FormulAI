"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronRight, FolderTree } from "lucide-react";
import DriverAvatar from "../../components/ui/DriverAvatar";
import { resolveDriver, prettyName } from "../../constants/drivers";

/* ═══════════════════════════════════════════════════════════════════════
   PREDICTION LOG

   The raw record: every round the model has scored, and for each one the
   full probability ranking it gave every driver against who actually stood
   on the podium. The dossier (on the map) tells the story of one race;
   this is the underlying log across the whole season, browsable the way a
   file tree is — year, then round, then the comparison itself.
   ═══════════════════════════════════════════════════════════════════════ */

export type LogRound = {
    round: number;
    raceName: string;
    correct: number;
    brierScore: number;
    predicted: string[];
    actual: string[];
    probabilities: Record<string, number>;
    isFuture?: boolean;
};

export type LogSeason = {
    season: number;
    rounds: LogRound[];
};

const pct = (p: number) => `${(p * 100).toFixed(1)}%`;

export default function PredictionLog({ seasons }: { seasons: LogSeason[] }) {
    // Only the most recent season starts open — the tree is meant to be
    // browsed one year at a time, not dumped onto the page all expanded.
    const [openYear, setOpenYear] = useState<number | null>(
        seasons[0]?.season ?? null
    );
    // Keyed "season-round" — round numbers repeat across years, so a bare
    // round number would open R1 in every season at once.
    const [openRoundKey, setOpenRoundKey] = useState<string | null>(null);

    return (
        <div className="rounded-[var(--radius-card)] border border-line bg-ink-2 overflow-hidden">
            {seasons.map((yearData) => (
                <YearNode
                    key={yearData.season}
                    data={yearData}
                    open={openYear === yearData.season}
                    onToggleYear={() =>
                        setOpenYear((cur) =>
                            cur === yearData.season ? null : yearData.season
                        )
                    }
                    openRound={
                        openRoundKey?.startsWith(`${yearData.season}-`)
                            ? Number(openRoundKey.split("-")[1])
                            : null
                    }
                    onToggleRound={(round) => {
                        const key = `${yearData.season}-${round}`;
                        setOpenRoundKey((cur) => (cur === key ? null : key));
                    }}
                />
            ))}
        </div>
    );
}

/* ═══════════════════════════════════════════════════════════════════════
   ONE YEAR
   ═══════════════════════════════════════════════════════════════════════ */

function YearNode({
    data,
    open,
    onToggleYear,
    openRound,
    onToggleRound,
}: {
    data: LogSeason;
    open: boolean;
    onToggleYear: () => void;
    openRound: number | null;
    onToggleRound: (round: number) => void;
}) {
    const scoredCount = data.rounds.filter((r) => !r.isFuture).length;

    return (
        <div className="border-b border-line last:border-b-0">
            <button
                type="button"
                onClick={onToggleYear}
                className="w-full flex items-center gap-2.5 px-4 py-3.5
                           bg-ink-1/60 hover:bg-ink-1 transition-colors text-left"
            >
                {open ? (
                    <ChevronDown className="w-4 h-4 text-fg-muted shrink-0" />
                ) : (
                    <ChevronRight className="w-4 h-4 text-fg-muted shrink-0" />
                )}
                <FolderTree className="w-4 h-4 text-accent shrink-0" />
                <span className="h-card text-fg">{data.season} season</span>
                <span className="label-xs ml-auto">
                    {scoredCount} round{scoredCount === 1 ? "" : "s"} scored
                </span>
            </button>

            {open && (
                <div className="flex flex-col border-t border-line">
                    {data.rounds.length === 0 ? (
                        <p className="px-9 py-3 text-[12px] text-fg-subtle">
                            No scored rounds recorded for {data.season}.
                        </p>
                    ) : (
                        data.rounds.map((round) => (
                            <RoundNode
                                key={round.round}
                                round={round}
                                open={openRound === round.round}
                                onToggle={() => onToggleRound(round.round)}
                            />
                        ))
                    )}
                </div>
            )}
        </div>
    );
}

/* ═══════════════════════════════════════════════════════════════════════
   ONE ROUND
   ═══════════════════════════════════════════════════════════════════════ */

function RoundNode({
    round,
    open,
    onToggle,
}: {
    round: LogRound;
    open: boolean;
    onToggle: () => void;
}) {
    const disabled = round.isFuture;

    return (
        <div className="border-b border-line last:border-b-0">
            <button
                type="button"
                onClick={disabled ? undefined : onToggle}
                disabled={disabled}
                className={`w-full flex items-center gap-2.5 pl-9 pr-4 py-2.5 text-left
                            transition-colors
                            ${disabled ? "cursor-default opacity-50" : "hover:bg-ink-1"}`}
            >
                {disabled ? (
                    <span className="w-4 h-4 shrink-0" />
                ) : open ? (
                    <ChevronDown className="w-3.5 h-3.5 text-fg-muted shrink-0" />
                ) : (
                    <ChevronRight className="w-3.5 h-3.5 text-fg-muted shrink-0" />
                )}
                <span className="label-xs w-8 shrink-0">R{round.round}</span>
                <span className="text-[13px] font-semibold text-fg truncate flex-1 min-w-0">
                    {round.raceName}
                </span>
                {disabled ? (
                    <span className="label-xs shrink-0">Not raced yet</span>
                ) : (
                    <>
                        <span
                            className={`shrink-0 px-2 py-0.5 rounded-full border text-[10px]
                                        font-black uppercase tracking-[0.1em] ${
                                            round.correct === 3
                                                ? "text-good border-good/30 bg-good/10"
                                                : round.correct === 2
                                                ? "text-warn border-warn/30 bg-warn/10"
                                                : round.correct === 1
                                                ? "text-[#60a5fa] border-[#60a5fa]/30 bg-[#60a5fa]/10"
                                                : "text-accent-hot border-accent-hot/30 bg-accent-hot/10"
                                        }`}
                        >
                            {round.correct}/3
                        </span>
                        <span className="label-xs shrink-0 w-20 text-right">
                            Brier {round.brierScore.toFixed(3)}
                        </span>
                    </>
                )}
            </button>

            <AnimatePresence initial={false}>
                {open && !disabled && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.22, ease: "easeOut" }}
                        className="overflow-hidden"
                    >
                        <RoundComparison round={round} />
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

/* ═══════════════════════════════════════════════════════════════════════
   THE COMPARISON — full field, ranked by the model's own probability,
   actual podium finish laid alongside.
   ═══════════════════════════════════════════════════════════════════════ */

function RoundComparison({ round }: { round: LogRound }) {
    const ranked = Object.entries(round.probabilities).sort((a, b) => b[1] - a[1]);
    const peak = ranked.length ? ranked[0][1] : 0.01;

    return (
        <div className="pl-9 pr-4 pb-4 pt-1">
            <div className="rounded-[var(--radius-chip)] border border-line bg-ink-1 overflow-hidden">
                <div className="grid grid-cols-[2rem_1fr_5rem_3.5rem] gap-2 px-3 py-2
                                border-b border-line label-xs">
                    <span>Rank</span>
                    <span>Driver — model's podium odds</span>
                    <span className="text-right">Prob.</span>
                    <span className="text-right">Finish</span>
                </div>
                <div className="max-h-[360px] overflow-y-auto">
                    {ranked.map(([driverId, prob], i) => {
                        const finishIndex = round.actual.indexOf(driverId);
                        const onPodium = finishIndex >= 0;
                        const driver = resolveDriver(driverId);

                        return (
                            <div
                                key={driverId}
                                className={`grid grid-cols-[2rem_1fr_5rem_3.5rem] gap-2 px-3 py-2
                                            items-center border-b border-line/50 last:border-b-0
                                            ${onPodium ? "bg-good/5" : ""}`}
                            >
                                <span className="text-[11px] font-mono text-fg-subtle num">
                                    {i + 1}
                                </span>
                                <span className="flex items-center gap-2 min-w-0">
                                    <DriverAvatar driverKey={driverId} size={20} />
                                    <span className="text-[12px] font-semibold text-fg truncate">
                                        {driver?.name ?? prettyName(driverId)}
                                    </span>
                                    <span className="flex-1 h-1 rounded-full bg-ink-4 overflow-hidden min-w-[24px]">
                                        <span
                                            className="block h-full rounded-full bg-accent/70"
                                            style={{ width: `${Math.min(100, (prob / peak) * 100)}%` }}
                                        />
                                    </span>
                                </span>
                                <span className="text-[11px] font-mono text-fg-muted num text-right">
                                    {pct(prob)}
                                </span>
                                <span
                                    className={`text-[11px] font-bold text-right ${
                                        onPodium ? "text-good" : "text-fg-subtle"
                                    }`}
                                >
                                    {onPodium ? `P${finishIndex + 1}` : "—"}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
