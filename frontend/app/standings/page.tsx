"use client";

import { useEffect, useMemo, useState } from "react";
import DriverAvatar from "../components/ui/DriverAvatar";
import { resolveDriver, prettyName, TEAM_LOGOS } from "../constants/drivers";
import {
    fetchSeasonResults,
    computeStandings,
    computeConstructorStandings,
    RoundResult,
} from "../lib/season";
import { SectionHeading, Placeholder, EmptyState } from "../components/ui/Primitives";

/**
 * Standings — driver and constructor tables from the same season results the
 * dashboard's Season form chart uses, so the two pages can't disagree.
 *
 * The previous version of this page read mock arrays and matched portraits
 * against the filesystem at request time by fuzzy-matching first-name +
 * last-name substrings against actual filenames (`kim` + `ant` for "Kimi
 * Antonelli"). That's exactly why Antonelli's avatar was broken — the asset
 * is `2025mercedesandant01right.avif`, keyed to "Andrea" (his full legal
 * first name), not "Kimi". Routing through the shared driver registry here
 * fixes it, since resolution goes through explicit ids rather than
 * re-guessing a filename convention per render.
 */

export default function StandingsPage() {
    const [seasonRounds, setSeasonRounds] = useState<RoundResult[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        (async () => {
            try {
                setSeasonRounds(await fetchSeasonResults(2026));
            } catch (err) {
                console.error("Failed to fetch season results:", err);
            } finally {
                setLoading(false);
            }
        })();
    }, []);

    const driverStandings = useMemo(
        () => computeStandings(seasonRounds),
        [seasonRounds]
    );
    const constructorStandings = useMemo(
        () => computeConstructorStandings(seasonRounds),
        [seasonRounds]
    );

    const lastRound = seasonRounds[seasonRounds.length - 1];

    return (
        <div className="max-w-[1500px] mx-auto pb-10">
            <div className="mb-6">
                <h1 className="h-display text-fg mb-2">Standings</h1>
                {lastRound ? (
                    <p className="label-xs">
                        After round {lastRound.round} — {lastRound.raceName}
                        {lastRound.circuitName ? ` · ${lastRound.circuitName}` : ""}
                    </p>
                ) : (
                    <p className="label-xs">2026 season</p>
                )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Drivers */}
                <section className="card p-5 sm:p-6">
                    <SectionHeading title="Drivers" meta={`${driverStandings.length || "—"} entries`} />

                    {driverStandings.length > 0 ? (
                        <div className="flex flex-col gap-2">
                            {driverStandings.map((row, i) => {
                                const d = resolveDriver(row.driverId);
                                const logo = d ? TEAM_LOGOS[d.team] : undefined;
                                return (
                                    <div
                                        key={row.driverId}
                                        className="card-raised card-interactive flex items-center gap-3 p-3"
                                    >
                                        <span className="w-6 text-[14px] font-bold text-fg-subtle num shrink-0 text-center">
                                            {i + 1}
                                        </span>
                                        <DriverAvatar driverKey={row.driverId} size={40} ring />
                                        <div className="min-w-0 flex-1">
                                            <p className="text-[14px] font-semibold text-fg truncate">
                                                {d?.name ?? prettyName(row.driverId)}
                                            </p>
                                            {/* Nationality rather than team name here — the
                                                logo to the right already carries team identity,
                                                so this line can carry different information
                                                instead of repeating it in text. */}
                                            <p className="text-[11px] text-fg-muted truncate">
                                                {d?.nationality ?? "—"}
                                            </p>
                                        </div>
                                        {/* Team badge on the driver row — the constructor's
                                            own mark, not just their name in text. */}
                                        {logo && (
                                            <img
                                                src={logo}
                                                alt=""
                                                aria-hidden
                                                className="w-6 h-6 object-contain opacity-50 shrink-0"
                                            />
                                        )}
                                        <span className="text-[16px] font-bold text-fg num shrink-0 w-10 text-right">
                                            {row.points}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    ) : loading ? (
                        <Placeholder lines={6} />
                    ) : (
                        <EmptyState message="No results yet this season." />
                    )}
                </section>

                {/* Constructors */}
                <section className="card p-5 sm:p-6">
                    <SectionHeading title="Constructors" meta={`${constructorStandings.length || "—"} teams`} />

                    {constructorStandings.length > 0 ? (
                        <div className="flex flex-col gap-2">
                            {constructorStandings.map((row, i) => {
                                const logo = TEAM_LOGOS[row.name];
                                return (
                                    <div
                                        key={row.constructorId}
                                        className="card-raised card-interactive flex items-center gap-3 p-3"
                                    >
                                        <span className="w-6 text-[14px] font-bold text-fg-subtle num shrink-0 text-center">
                                            {i + 1}
                                        </span>
                                        {/* Symbol — name — points. */}
                                        <div className="w-9 h-9 rounded-full bg-ink-4 grid place-items-center shrink-0">
                                            {logo ? (
                                                <img
                                                    src={logo}
                                                    alt=""
                                                    aria-hidden
                                                    className="w-6 h-6 object-contain"
                                                />
                                            ) : (
                                                <span className="text-[11px] font-bold text-fg-subtle">
                                                    {row.name.slice(0, 2).toUpperCase()}
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-[14px] font-semibold text-fg flex-1 truncate">
                                            {row.name}
                                        </p>
                                        <span className="text-[16px] font-bold text-fg num shrink-0 w-10 text-right">
                                            {row.points}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    ) : loading ? (
                        <Placeholder lines={6} />
                    ) : (
                        <EmptyState message="No results yet this season." />
                    )}
                </section>
            </div>
        </div>
    );
}
