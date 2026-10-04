"use client";

import { useEffect, useMemo, useState } from "react";
import TracksExplorer from "./TracksExplorer";
import {
    CIRCUITS,
    CIRCUIT_SLUG_BY_JOLPICA_ID,
    fetchSeasonSchedule,
    ScheduleEntry,
} from "../lib/circuits";
import { Placeholder } from "../components/ui/Primitives";

const SEASON = 2026;

export default function TracksPage() {
    const [schedule, setSchedule] = useState<ScheduleEntry[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        (async () => {
            try {
                setSchedule(await fetchSeasonSchedule(SEASON));
            } catch (err) {
                console.error("Failed to fetch season schedule:", err);
            } finally {
                setLoading(false);
            }
        })();
    }, []);

    /** slug -> this year's round for that circuit, if any. */
    const scheduleBySlug = useMemo(() => {
        const map = new Map<string, ScheduleEntry>();
        for (const entry of schedule) {
            const slug = CIRCUIT_SLUG_BY_JOLPICA_ID[entry.circuitId];
            if (slug) map.set(slug, entry);
        }
        return map;
    }, [schedule]);

    const today = useMemo(() => new Date(), []);

    const tracks = useMemo(() => {
        const fromRegistry = CIRCUITS.map((c) => {
            const round = scheduleBySlug.get(c.slug);
            const onCalendar = !!round;
            const completed = round ? new Date(round.date) < today : false;
            return { ...c, round, onCalendar, completed, lat: round?.lat || 0, long: round?.long || 0 };
        });

        /* Rounds the registry has no artwork for (Sepang, round 16) are still
           rounds — on a page that *is* the season map, dropping one would
           leave a silent hole in the calendar. They get a marker and a panel
           that says the art is missing, rather than no marker at all. */
        const known = new Set(CIRCUITS.map((c) => c.slug));
        const unmapped = schedule
            .filter((entry) => {
                const slug = CIRCUIT_SLUG_BY_JOLPICA_ID[entry.circuitId];
                return (!slug || !known.has(slug)) && (entry.lat !== 0 || entry.long !== 0);
            })
            .map((entry) => ({
                slug: `round-${entry.round}`,
                /* Only strip the suffix when that's all it is: round 16 is the
                   "Bahrain Grand Prix in Malaysia", and cutting at "Grand Prix"
                   would label a race at Sepang as Bahrain. */
                locality: entry.raceName.replace(/ Grand Prix$/, ""),
                name: entry.circuitId
                    .split("_")
                    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                    .join(" "),
                img: "",
                round: entry,
                onCalendar: true,
                completed: new Date(entry.date) < today,
                lat: entry.lat,
                long: entry.long,
            }));

        return [...fromRegistry, ...unmapped];
    }, [scheduleBySlug, schedule, today]);

    return (
        <div className="max-w-[1500px] mx-auto pb-10">
            <div className="mb-6">
                <h1 className="h-display text-fg mb-2">Circuits</h1>
                <p className="label-xs">
                    {SEASON} calendar — pick a marker to open that circuit's
                    layout
                </p>
            </div>

            {loading && schedule.length === 0 ? (
                <div className="card p-6"><Placeholder lines={5} /></div>
            ) : (
                <TracksExplorer tracks={tracks} season={SEASON} />
            )}
        </div>
    );
}
