"use client";

import { motion } from "framer-motion";
import { ArrowLeft, Check, MoveVertical, X } from "lucide-react";
import DriverAvatar from "../../components/ui/DriverAvatar";
import { resolveDriver, prettyName, TEAM_LOGOS } from "../../constants/drivers";
import { CIRCUITS } from "../../lib/circuits";
import type { RaceMapLocation } from "../../components/ui/RaceMap";

/* ═══════════════════════════════════════════════════════════════════════
   RACE DOSSIER

   What the model said about one past round, opened by clicking that
   round's marker on the season map.

   The question this answers, per podium step, is three-deep: did the model
   have this driver on the podium at all, did it have them on *this* step,
   and if not — who did it put here instead, and how sure was it? A bare
   "2/3 correct" badge hides all of that.
   ═══════════════════════════════════════════════════════════════════════ */

export type RaceResult = {
    /** Model's predicted podium, in order. */
    predicted: string[];
    /** Who actually finished P1–P3. */
    actual: string[];
    correct: number;
    brierScore: number;
    /** Per-driver podium probability for this round. */
    probabilities: Record<string, number>;
};

type Verdict = "exact" | "podium" | "missed";

const MEDAL: Record<number, { color: string; label: string }> = {
    1: { color: "#facc15", label: "P1" },
    2: { color: "#d1d5db", label: "P2" },
    3: { color: "#d97706", label: "P3" },
};

const VERDICT_STYLE: Record<Verdict, { text: string; className: string }> = {
    exact: {
        text: "Called exactly",
        className: "text-good border-good/30 bg-good/10",
    },
    podium: {
        text: "Podium, wrong step",
        className: "text-warn border-warn/30 bg-warn/10",
    },
    missed: {
        text: "Not predicted",
        className: "text-accent-hot border-accent-hot/30 bg-accent-hot/10",
    },
};

const pct = (p: number | undefined) =>
    p == null ? "—" : `${(p * 100).toFixed(1)}%`;

/** Where a driver actually finished, as a label. */
const finishLabel = (index: number) =>
    index >= 0 ? `finished P${index + 1}` : "finished off the podium";

export default function RaceDossier({
    location,
    result,
    onClose,
}: {
    location: RaceMapLocation;
    result: RaceResult;
    onClose: () => void;
}) {
    // Bars are scaled against the strongest call of this race, not against
    // 100% — every driver's podium probability sits in the low single
    // digits, so an absolute scale renders three identical slivers.
    const peak = Math.max(
        ...result.actual.concat(result.predicted).map((d) => result.probabilities?.[d] ?? 0),
        0.01
    );

    // The circuit's layout art, by the same slug the map marker carries.
    const circuit = CIRCUITS.find((c) => c.slug === location.slug);

    const accuracy =
        result.correct === 3
            ? "text-good border-good/30 bg-good/10"
            : result.correct === 2
            ? "text-warn border-warn/30 bg-warn/10"
            : result.correct === 1
            ? "text-[#60a5fa] border-[#60a5fa]/30 bg-[#60a5fa]/10"
            : "text-accent-hot border-accent-hot/30 bg-accent-hot/10";

    return (
        <div className="flex flex-col h-full">
            {/* ── Header ──────────────────────────────────────────── */}
            <div className="shrink-0 px-5 pt-5 pb-4 border-b border-line">
                <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                        <p className="label-xs">
                            {location.round != null && `Round ${location.round} · `}
                            {location.date &&
                                new Date(location.date).toLocaleDateString("en-GB", {
                                    day: "numeric",
                                    month: "long",
                                })}
                        </p>
                        <h3 className="h-section text-fg mt-1 truncate">
                            {location.locality}
                        </h3>
                        <p className="text-[13px] text-fg-muted truncate">
                            {location.name}
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        aria-label="Back to the map"
                        className="shrink-0 grid place-items-center w-8 h-8
                                   rounded-[var(--radius-chip)] border border-line
                                   text-fg-muted hover:text-fg hover:bg-ink-4
                                   transition-colors"
                    >
                        <ArrowLeft className="w-4 h-4" />
                    </button>
                </div>

                <div className="flex flex-wrap items-center gap-2 mt-3">
                    <span
                        className={`px-2.5 py-1 rounded-full border text-[10px] font-black
                                    uppercase tracking-[0.14em] ${accuracy}`}
                    >
                        {result.correct}/3 called
                    </span>
                    <span className="px-2.5 py-1 rounded-full border border-line
                                     text-[10px] font-black uppercase tracking-[0.14em]
                                     text-fg-muted">
                        Brier {result.brierScore.toFixed(3)}
                    </span>
                </div>
            </div>

            {/* ── Podium, step by step ────────────────────────────── */}
            <div className="flex-1 min-h-0 overflow-y-auto px-5 py-4 flex flex-col gap-3">
                {/* The circuit itself, so the dossier says *where* before it
                    says who — same layout art the Circuits page uses. */}
                {circuit?.img && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.3 }}
                        className="rounded-[var(--radius-chip)] border border-line
                                   bg-ink-1 px-4 py-3"
                    >
                        <p className="label-xs mb-2">Circuit layout</p>
                        <img
                            src={circuit.img}
                            alt={`${circuit.name} layout`}
                            loading="lazy"
                            className="w-full h-[130px] object-contain opacity-80"
                        />
                    </motion.div>
                )}

                {result.actual.slice(0, 3).map((driverId, slot) => {
                    const predictedIndex = result.predicted.indexOf(driverId);
                    const verdict: Verdict =
                        predictedIndex === slot
                            ? "exact"
                            : predictedIndex >= 0
                            ? "podium"
                            : "missed";

                    // Who the model actually put on this step, and how that
                    // pick turned out.
                    const modelPick = result.predicted[slot];
                    const modelPickFinish = result.actual.indexOf(modelPick);

                    return (
                        <PodiumStep
                            key={`${driverId}-${slot}`}
                            slot={slot}
                            driverId={driverId}
                            verdict={verdict}
                            predictedIndex={predictedIndex}
                            probability={result.probabilities?.[driverId]}
                            peak={peak}
                            modelPick={verdict === "exact" ? null : modelPick}
                            modelPickProbability={result.probabilities?.[modelPick]}
                            modelPickFinish={modelPickFinish}
                        />
                    );
                })}

                {/* ── The model's own call, for reference ─────────── */}
                <div className="mt-1 rounded-[var(--radius-chip)] border border-line bg-ink-1 p-4">
                    <p className="label-xs mb-3">What the model predicted</p>
                    <div className="flex flex-col gap-2">
                        {result.predicted.slice(0, 3).map((driverId, i) => {
                            const finish = result.actual.indexOf(driverId);
                            const onPodium = finish >= 0;
                            const exact = finish === i;
                            const driver = resolveDriver(driverId);

                            return (
                                <div
                                    key={`${driverId}-pred-${i}`}
                                    className="flex items-center gap-2.5"
                                >
                                    <span className="label-xs w-5 shrink-0">
                                        P{i + 1}
                                    </span>
                                    <DriverAvatar driverKey={driverId} size={24} />
                                    <span className="text-[13px] font-semibold text-fg truncate flex-1 min-w-0">
                                        {driver?.name ?? prettyName(driverId)}
                                    </span>
                                    <span
                                        className={`flex items-center gap-1 text-[11px] font-bold shrink-0 ${
                                            exact
                                                ? "text-good"
                                                : onPodium
                                                ? "text-warn"
                                                : "text-fg-subtle"
                                        }`}
                                    >
                                        {exact ? (
                                            <>
                                                <Check className="w-3.5 h-3.5" /> P{finish + 1}
                                            </>
                                        ) : onPodium ? (
                                            <>
                                                <MoveVertical className="w-3.5 h-3.5" /> P
                                                {finish + 1}
                                            </>
                                        ) : (
                                            <>
                                                <X className="w-3.5 h-3.5" /> Off podium
                                            </>
                                        )}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
}

/* ═══════════════════════════════════════════════════════════════════════
   ONE PODIUM STEP
   ═══════════════════════════════════════════════════════════════════════ */

function PodiumStep({
    slot,
    driverId,
    verdict,
    predictedIndex,
    probability,
    peak,
    modelPick,
    modelPickProbability,
    modelPickFinish,
}: {
    slot: number;
    driverId: string;
    verdict: Verdict;
    predictedIndex: number;
    probability?: number;
    peak: number;
    modelPick: string | null;
    modelPickProbability?: number;
    modelPickFinish: number;
}) {
    const position = slot + 1;
    const medal = MEDAL[position];
    const driver = resolveDriver(driverId);
    const logo = driver ? TEAM_LOGOS[driver.team] : undefined;
    const style = VERDICT_STYLE[verdict];

    return (
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * slot, duration: 0.28, ease: "easeOut" }}
            className="rounded-[var(--radius-chip)] border border-line bg-ink-1 overflow-hidden"
        >
            <div className="flex items-center gap-3 p-3.5">
                {/* Position badge in medal colour — a podium step should read
                    as 1st/2nd/3rd before it reads as anything else. */}
                <span
                    className="grid place-items-center w-7 h-7 rounded-full shrink-0
                               text-[12px] font-black text-ink-0"
                    style={{ backgroundColor: medal.color }}
                >
                    {position}
                </span>

                <DriverAvatar driverKey={driverId} size={44} ring />

                <div className="flex-1 min-w-0">
                    <p className="text-[15px] font-bold text-fg truncate leading-tight">
                        {driver?.name ?? prettyName(driverId)}
                    </p>
                    <span className="flex items-center gap-1.5 mt-0.5">
                        {logo && (
                            <img
                                src={logo}
                                alt=""
                                aria-hidden
                                className="h-3 object-contain brightness-0 invert opacity-50"
                            />
                        )}
                        <span className="label-xs truncate">
                            {driver?.team ?? "—"}
                        </span>
                    </span>
                </div>

                <span
                    className={`shrink-0 px-2 py-1 rounded-full border text-[9px]
                                font-black uppercase tracking-[0.12em] ${style.className}`}
                >
                    {style.text}
                </span>
            </div>

            {/* Model confidence in the driver who actually finished here. */}
            <div className="px-3.5 pb-3">
                <div className="flex items-center justify-between mb-1.5">
                    <span className="label-xs">Model gave them</span>
                    <span className="text-[12px] font-mono font-bold text-fg num">
                        {pct(probability)}
                    </span>
                </div>
                <div className="h-1.5 rounded-full bg-ink-4 overflow-hidden">
                    <motion.div
                        className="h-full rounded-full"
                        style={{ backgroundColor: medal.color }}
                        initial={{ width: 0 }}
                        animate={{
                            width: `${Math.min(100, ((probability ?? 0) / peak) * 100)}%`,
                        }}
                        transition={{ duration: 0.5, delay: 0.1 + 0.05 * slot, ease: "easeOut" }}
                    />
                </div>
            </div>

            {/* The correction: what the model had on this step instead, and
                where that driver really came home. */}
            {modelPick && (
                <div className="flex items-center gap-2.5 px-3.5 py-2.5
                                border-t border-line bg-ink-2">
                    <DriverAvatar driverKey={modelPick} size={22} />
                    <p className="text-[11px] text-fg-muted leading-snug flex-1 min-w-0">
                        Model put{" "}
                        <span className="font-bold text-fg">
                            {resolveDriver(modelPick)?.name ?? prettyName(modelPick)}
                        </span>{" "}
                        on P{position} at{" "}
                        <span className="font-mono font-bold text-fg num">
                            {pct(modelPickProbability)}
                        </span>{" "}
                        — {finishLabel(modelPickFinish)}.
                        {verdict === "podium" && (
                            <>
                                {" "}
                                It had this driver at{" "}
                                <span className="font-bold text-fg">
                                    P{predictedIndex + 1}
                                </span>
                                .
                            </>
                        )}
                    </p>
                </div>
            )}
        </motion.div>
    );
}
