"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { ChevronRight, ChevronDown, ChevronUp } from "lucide-react";

import TopBar from "./components/TopBar";
import RaceFilmstrip, { RaceCard } from "./components/RaceFilmstrip";
import DotGrid from "./components/ui/DotGrid";
import DriverAvatar from "./components/ui/DriverAvatar";
import PositionTrace from "./components/ui/PositionTrace";
import { resolveDriver, prettyName, TEAM_LOGOS } from "./constants/drivers";
import {
  fetchSeasonResults,
  toDriverSeries,
  buildRoundLabels,
  computeStandings,
  RoundResult,
} from "./lib/season";
import {
  SectionHeading,
  Badge,
  StatTile,
  Placeholder,
  EmptyState,
} from "./components/ui/Primitives";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://akhil-008-formulai-backend-api.hf.space";

/* Constructor points are still placeholder — the driver standings are now
   derived from real results, so don't add hardcoded driver rows here or the
   rail will contradict the chart. */
const TOP_CONSTRUCTORS = [
  { name: "Mercedes", points: 135, color: "#00D2BE" },
  { name: "Ferrari", points: 90, color: "#E80020" },
  { name: "McLaren", points: 56, color: "#FF8000" },
];

function useCountdown(targetDate: string) {
  const [timeLeft, setTimeLeft] = useState({ days: 0, hours: 0, minutes: 0, seconds: 0 });

  useEffect(() => {
    const target = new Date(targetDate).getTime();
    const tick = () => {
      const diff = target - Date.now();
      if (diff > 0) {
        setTimeLeft({
          days: Math.floor(diff / 86400000),
          hours: Math.floor((diff % 86400000) / 3600000),
          minutes: Math.floor((diff % 3600000) / 60000),
          seconds: Math.floor((diff % 60000) / 1000),
        });
      } else {
        setTimeLeft({ days: 0, hours: 0, minutes: 0, seconds: 0 });
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [targetDate]);

  return timeLeft;
}

function toCard(r: any, round: number): RaceCard {
  const d = new Date(`${r.date}T${r.time || "00:00:00Z"}`);
  return {
    round,
    name: r.raceName,
    circuit: r.Circuit?.circuitName,
    dateString: d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" }),
  };
}

export default function Home() {
  const [races, setRaces] = useState<any[]>([]);
  const [nextIdx, setNextIdx] = useState<number>(-1);
  const [evaluation, setEvaluation] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [prevWinner, setPrevWinner] = useState<string | null>(null);
  const [seasonRounds, setSeasonRounds] = useState<RoundResult[]>([]);
  const [resultsLoading, setResultsLoading] = useState(true);
  const [standingsExpanded, setStandingsExpanded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("https://api.jolpi.ca/ergast/f1/2026.json");
        const data = await res.json();
        const list = data.MRData.RaceTable.Races ?? [];
        setRaces(list);

        const now = Date.now();
        let idx = list.findIndex(
          (r: any) => new Date(`${r.date}T${r.time || "00:00:00Z"}`).getTime() > now
        );
        if (idx < 0) idx = Math.max(list.length - 1, 0);
        setNextIdx(idx);
      } catch (err) {
        console.error("Failed to fetch F1 schedule:", err);
      } finally {
        setLoading(false);
      }
    })();

    (async () => {
      try {
        setSeasonRounds(await fetchSeasonResults(2026));
      } catch (err) {
        console.error("Failed to fetch season results:", err);
      } finally {
        setResultsLoading(false);
      }
    })();

    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/evaluation`);
        setEvaluation(await res.json());
      } catch (err) {
        console.error("Failed to fetch evaluation:", err);
      }
    })();
  }, []);

  const nextRace: RaceCard = useMemo(() => {
    if (nextIdx < 0 || !races[nextIdx]) {
      return { round: 0, name: "Loading season…", dateString: "—" };
    }
    const r = races[nextIdx];
    const d = new Date(`${r.date}T${r.time || "00:00:00Z"}`);
    return {
      round: Number(r.round),
      name: r.raceName,
      circuit: r.Circuit?.circuitName,
      dateString: d.toLocaleDateString("en-GB", {
        day: "2-digit", month: "long", year: "numeric",
      }),
    };
  }, [races, nextIdx]);

  /* Winner of the last completed round, for the left flank. */
  useEffect(() => {
    if (nextIdx <= 0 || !races[nextIdx - 1]) return;
    const round = races[nextIdx - 1].round;
    (async () => {
      try {
        const res = await fetch(
          `https://api.jolpi.ca/ergast/f1/2026/${round}/results.json?limit=1`
        );
        const data = await res.json();
        const winner =
          data?.MRData?.RaceTable?.Races?.[0]?.Results?.[0]?.Driver?.familyName;
        if (winner) setPrevWinner(`${winner} won`);
      } catch {
        /* Left flank falls back to "Result pending". */
      }
    })();
  }, [nextIdx, races]);

  const prevRace = nextIdx > 0
    ? { ...toCard(races[nextIdx - 1], Number(races[nextIdx - 1].round)), result: prevWinner ?? undefined }
    : null;
  const upcomingRace =
    nextIdx >= 0 && races[nextIdx + 1]
      ? toCard(races[nextIdx + 1], Number(races[nextIdx + 1].round))
      : null;

  /* Memoised, and the fallback is a fixed constant rather than
     `new Date()`. A fresh timestamp on every render changes the hook's
     dependency each pass, which re-runs the effect, sets state, and
     renders again — an infinite loop while the schedule is loading. */
  const targetDate = useMemo(() => {
    const r = races[nextIdx];
    if (!r) return "1970-01-01T00:00:00.000Z";
    return new Date(`${r.date}T${r.time || "00:00:00Z"}`).toISOString();
  }, [races, nextIdx]);

  const countdown = useCountdown(targetDate);

  /* Position-by-round for the whole field. */
  const traceRounds = useMemo(() => {
    const labels = buildRoundLabels(seasonRounds);
    return seasonRounds.map((r, i) => ({ round: r.round, label: labels[i] }));
  }, [seasonRounds]);

  const traceSeries = useMemo(
    () => toDriverSeries(seasonRounds),
    [seasonRounds]
  );

  /* Standings come from the same results the chart uses, so the rail and
     the legend can't disagree about who's second. */
  const standings = useMemo(
    () => computeStandings(seasonRounds),
    [seasonRounds]
  );

  /* Dashed extension to the next round. Sourced from the model's actual
     podium pick — nothing is drawn if the backend hasn't scored the race,
     rather than extrapolating a line the model didn't produce. */
  const projectedNext = useMemo(() => {
    const p = evaluation?.next_race?.prediction;
    if (!Array.isArray(p)) return undefined;
    return p.slice(0, 3).map((driverId: string, i: number) => ({
      driverId,
      position: i + 1,
    }));
  }, [evaluation]);

  const podium: { driver: string; prob: number }[] = useMemo(() => {
    const p = evaluation?.next_race?.prediction;
    const probs = evaluation?.next_race?.probabilities ?? {};
    if (!Array.isArray(p)) return [];
    return p.slice(0, 3).map((d: string) => ({
      driver: d,
      prob: typeof probs[d] === "number" ? probs[d] : 0,
    }));
  }, [evaluation]);

  const seasonAccuracy =
    typeof evaluation?.avg_correct_out_of_3 === "number"
      ? evaluation.avg_correct_out_of_3
      : null;

  return (
    <div className="max-w-[1500px] mx-auto pb-10">
      <TopBar driversOnGrid={20} driversTotal={20} teamCount={10} />

      <RaceFilmstrip
        previous={prevRace}
        next={nextRace}
        upcoming={upcomingRace}
        countdown={countdown}
      />

      {/* Body: main column + right rail */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_320px] gap-4 mt-4">
        <div className="min-w-0 flex flex-col gap-4">
          {/* Season shape — every driver, podium in focus */}
          <section className="card p-5 sm:p-6">
            <SectionHeading
              title="Season form"
              meta={`Finishing position · ${seasonRounds.length} rounds`}
              right={
                <Link
                  href="/results"
                  className="text-[12px] text-fg-muted hover:text-fg transition-colors
                             inline-flex items-center gap-1"
                >
                  All results <ChevronRight className="w-3.5 h-3.5" />
                </Link>
              }
            />

            {traceRounds.length > 0 ? (
              <PositionTrace
                rounds={traceRounds}
                series={traceSeries}
                projection={projectedNext}
              />
            ) : resultsLoading ? (
              <Placeholder lines={5} />
            ) : (
              <EmptyState message="No completed rounds yet this season." />
            )}
          </section>

          {/* Podium prediction cards */}
          <section>
            <SectionHeading title="Predicted podium" meta={nextRace.name} />

            {podium.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {podium.map((p, idx) => {
                  const d = resolveDriver(p.driver);
                  return (
                    <article
                      key={p.driver}
                      className="card card-interactive p-5 relative overflow-hidden"
                    >
                      {/* Team colour as a hairline at the top edge — identity
                          without the accent-rail-on-a-rounded-card cliché. */}
                      <span
                        className="absolute top-0 left-5 right-5 h-[2px] rounded-full"
                        style={{ backgroundColor: d?.color ?? "var(--color-line-strong)" }}
                        aria-hidden
                      />

                      <div className="flex items-start gap-3 mb-4">
                        <DriverAvatar driverKey={p.driver} size={44} ring />
                        <div className="min-w-0 flex-1">
                          <p className="label-xs mb-1">P{idx + 1}</p>
                          <h3 className="h-card text-fg truncate">
                            {d?.name ?? prettyName(p.driver)}
                          </h3>
                          <p
                            className="text-[11px] truncate"
                            style={{ color: d?.color ?? "var(--color-fg-muted)" }}
                          >
                            {d?.team ?? "—"}
                          </p>
                        </div>
                        <Badge tone={idx === 0 ? "accent" : "neutral"}>
                          {(p.prob * 100).toFixed(1)}%
                        </Badge>
                      </div>

                      <div className="pt-4 border-t border-line">
                        <p className="label-xs mb-2.5">Monte Carlo · 10k sims</p>
                        <DotGrid
                          probability={p.prob}
                          label={`${d?.name ?? p.driver}: ${(p.prob * 100).toFixed(1)}% of simulations end on the podium`}
                        />
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : loading ? (
              <div className="card p-6"><Placeholder lines={3} /></div>
            ) : (
              <div className="card p-6">
                <EmptyState message="Prediction unavailable — the backend hasn't scored this round yet." />
              </div>
            )}
          </section>
        </div>

        {/* Right rail */}
        <aside className="flex flex-col gap-4 min-w-0">
          <section className="card p-5">
            <SectionHeading title="Standings" meta="Drivers" />
            <div className="flex flex-col gap-2">
              {standings.length === 0 && resultsLoading && <Placeholder lines={3} />}
              {/* Always show top 3 */}
              {(standingsExpanded ? standings : standings.slice(0, 3)).map((row, i) => {
                const d = resolveDriver(row.driverId);
                return (
                  <div
                    key={row.driverId}
                    className="card-raised card-interactive flex items-center gap-3 p-3"
                  >
                    <span className="w-5 text-[13px] font-bold text-fg-subtle num shrink-0">
                      {i + 1}
                    </span>
                    <DriverAvatar driverKey={row.driverId} size={36} ring />
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-semibold text-fg truncate">
                        {d?.name ?? prettyName(row.driverId)}
                      </p>
                      <p
                        className="text-[11px] truncate"
                        style={{ color: d?.color ?? "var(--color-fg-muted)" }}
                      >
                        {d?.team ?? "—"}
                      </p>
                    </div>
                    <span className="text-[15px] font-bold text-fg num shrink-0">
                      {row.points}
                    </span>
                  </div>
                );
              })}
            </div>
            {/* Inline expand/collapse instead of navigating to a new page */}
            {standings.length > 3 && (
              <button
                onClick={() => setStandingsExpanded((v) => !v)}
                className="mt-3 w-full h-10 rounded-[var(--radius-chip)] bg-ink-3
                           hover:bg-ink-4 transition-colors text-[12px] font-semibold
                           text-fg-muted hover:text-fg inline-flex items-center justify-center gap-1"
              >
                {standingsExpanded ? (
                  <><ChevronUp className="w-3.5 h-3.5" /> Show less</>
                ) : (
                  <><ChevronDown className="w-3.5 h-3.5" /> All {standings.length} drivers</>
                )}
              </button>
            )}
          </section>

          <section className="card p-5">
            <SectionHeading title="Constructors" />
            <div className="flex flex-col gap-2">
              {TOP_CONSTRUCTORS.map((t, i) => {
                const logo = TEAM_LOGOS[t.name];
                return (
                  <div
                    key={t.name}
                    className="card-raised card-interactive flex items-center gap-3 p-3"
                  >
                    <span className="w-5 text-[13px] font-bold text-fg-subtle num shrink-0">
                      {i + 1}
                    </span>
                    <span
                      className="w-1.5 h-8 rounded-full shrink-0"
                      style={{ backgroundColor: t.color }}
                      aria-hidden
                    />
                    <p className="text-[13px] font-semibold text-fg flex-1 truncate">
                      {t.name}
                    </p>
                    {logo && (
                      <img
                        src={logo}
                        alt={`${t.name} logo`}
                        className="w-7 h-7 object-contain opacity-60 group-hover:opacity-100 transition-opacity shrink-0"
                      />
                    )}
                    <span className="text-[15px] font-bold text-fg num shrink-0">
                      {t.points}
                    </span>
                  </div>
                );
              })}
            </div>
          </section>

          <StatTile
            label="Season accuracy"
            value={seasonAccuracy != null ? `${seasonAccuracy.toFixed(2)}/3` : "—"}
            sub="Podium slots correct per race"
            accent
          />
        </aside>
      </div>
    </div>
  );
}
