"use client";

import { motion } from "framer-motion";
import { ChevronRight, Timer, Calendar, MapPin, Flag, Trophy, Target } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useState, useEffect } from "react";

// --- Custom Hook for Countdown ---
function useCountdown(targetDate: string) {
  const [timeLeft, setTimeLeft] = useState({ days: 0, hours: 0, minutes: 0, seconds: 0 });

  useEffect(() => {
    const target = new Date(targetDate).getTime();
    const interval = setInterval(() => {
      const now = new Date().getTime();
      const difference = target - now;

      if (difference > 0) {
        setTimeLeft({
          days: Math.floor(difference / (1000 * 60 * 60 * 24)),
          hours: Math.floor((difference % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)),
          minutes: Math.floor((difference % (1000 * 60 * 60)) / (1000 * 60)),
          seconds: Math.floor((difference % (1000 * 60)) / 1000)
        });
      } else {
        clearInterval(interval);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [targetDate]);

  return timeLeft;
}

// --- Mock Data ---
const TOP_DRIVERS = [
  { name: "Max Verstappen", points: 425, team: "Red Bull", color: "#0600EF", img: "/assets/Teams/Red Bull Racing/2025redbullracingmaxver01right.avif" },
  { name: "Lando Norris", points: 390, team: "McLaren", color: "#FF8000", img: "/assets/Teams/McLaren/2025mclarenlannor01right.avif" },
  { name: "Charles Leclerc", points: 345, team: "Ferrari", color: "#E80020", img: "/assets/Teams/Ferrari/2025ferrarichalec01right.avif" },
];

const TOP_CONSTRUCTORS = [
  { name: "McLaren", points: 680, color: "#FF8000", logo: "/assets/Teams/McLaren/2025mclarenlogowhite.avif" },
  { name: "Ferrari", points: 650, color: "#E80020", logo: "/assets/Teams/Ferrari/2025ferrarilogolight.avif" },
  { name: "Red Bull Racing", points: 590, color: "#0600EF", logo: "/assets/Teams/Red Bull Racing/2025redbullracinglogowhite.avif" },
];

export default function Home() {
  const countdown = useCountdown("2026-03-08T15:00:00Z"); // Bahrain GP Race Day

  return (
    <div className="flex flex-col gap-10 max-w-7xl mx-auto mb-20 animate-in fade-in duration-700">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <h1 className="text-4xl md:text-5xl font-black tracking-tight text-white italic" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>
          Dashboard
        </h1>
        <p className="text-f1-muted text-lg italic tracking-wider font-semibold" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>
          Your 2026 unified command center.
        </p>
      </div>

      {/* Hero Banner: Dynamic Countdown */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative w-full rounded-3xl overflow-hidden glass-card group flex flex-col justify-end border-t border-white/10 shadow-2xl min-h-[400px]"
      >
        <div className="absolute inset-0 bg-gradient-to-br from-f1-red/20 via-transparent to-f1-teal/10 opacity-50" />
        <div
          className="absolute inset-0 bg-cover bg-center transition-transform duration-1000 group-hover:scale-105 opacity-50 filter grayscale-[0.3]"
          style={{ backgroundImage: 'url("/assets/hero_bg.webp")' }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-f1-navy via-f1-navy/60 to-transparent" />

        <div className="relative z-10 p-10 flex flex-col md:flex-row items-end justify-between w-full h-full gap-8">
          <div className="flex flex-col gap-4">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-f1-red/20 border border-f1-red/30 text-f1-red font-bold text-sm backdrop-blur-md uppercase tracking-widest w-fit">
              <span className="w-2.5 h-2.5 rounded-full bg-f1-red animate-pulse" />
              Upcoming Race
            </div>
            <div>
              <h2 className="text-5xl md:text-6xl font-black text-white italic tracking-tighter uppercase mb-2">Bahrain GP</h2>
              <p className="text-xl font-medium text-white/80 flex items-center gap-2">
                <Calendar className="w-5 h-5 text-f1-papaya" /> March 06 - 08, 2026
              </p>
            </div>
          </div>

          {/* Countdown Clock */}
          <div className="flex flex-col items-center md:items-end gap-4 glass-panel p-6 rounded-2xl border border-white/10 backdrop-blur-xl">
            <p className="text-xs font-bold tracking-widest text-f1-muted uppercase">Lights Out In</p>
            <div className="flex gap-4 md:gap-6 text-center">
              <div className="flex flex-col">
                <span className="text-4xl md:text-5xl font-black text-white font-mono">{String(countdown.days).padStart(2, '0')}</span>
                <span className="text-xs font-bold text-f1-muted tracking-widest mt-1">Days</span>
              </div>
              <span className="text-4xl md:text-5xl font-black text-white/30">:</span>
              <div className="flex flex-col">
                <span className="text-4xl md:text-5xl font-black text-white font-mono">{String(countdown.hours).padStart(2, '0')}</span>
                <span className="text-xs font-bold text-f1-muted tracking-widest mt-1">Hrs</span>
              </div>
              <span className="text-4xl md:text-5xl font-black text-white/30">:</span>
              <div className="flex flex-col">
                <span className="text-4xl md:text-5xl font-black text-white font-mono">{String(countdown.minutes).padStart(2, '0')}</span>
                <span className="text-xs font-bold text-f1-muted tracking-widest mt-1">Min</span>
              </div>
              <span className="text-4xl md:text-5xl font-black text-white/30">:</span>
              <div className="flex flex-col">
                <span className="text-4xl md:text-5xl font-black text-f1-papaya font-mono">{String(countdown.seconds).padStart(2, '0')}</span>
                <span className="text-xs font-bold text-f1-muted tracking-widest mt-1">Sec</span>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Grid Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* Next Race Spotlight */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="lg:col-span-1 glass-card p-8 flex flex-col gap-6"
        >
          <div className="flex justify-between items-center border-b border-white/10 pb-4">
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <MapPin className="w-5 h-5 text-f1-papaya" /> Event Spotlight
            </h3>
            <span className="text-xs font-bold px-2 py-1 rounded bg-white/10 text-white/80 uppercase">Round 1</span>
          </div>

          <div className="relative w-full h-48 bg-white/5 rounded-xl flex items-center justify-center p-4 border border-white/5">
            <Image
              src="/assets/Circuit/2026tracksakhirdetailed.avif"
              alt="Bahrain Track Map"
              fill
              className="object-contain filter invert opacity-80"
              unoptimized
            />
          </div>

          <div className="flex flex-col gap-4">
            <div className="flex justify-between items-center">
              <span className="text-f1-muted text-sm font-semibold tracking-widest uppercase">Circuit length</span>
              <span className="text-white font-bold">5.412 km</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-f1-muted text-sm font-semibold tracking-widest uppercase">Race distance</span>
              <span className="text-white font-bold">308.238 km</span>
            </div>
            <div className="flex flex-col gap-1 mt-2">
              <span className="text-f1-muted text-sm font-semibold tracking-widest uppercase">Lap Record</span>
              <span className="text-white font-bold">1:31.447 <span className="text-white/50 text-sm font-normal">(Pedro de la Rosa, 2005)</span></span>
            </div>
          </div>

          <Link href="/schedule" className="mt-auto w-full py-3 rounded-xl bg-white/5 border border-white/10 text-white font-bold text-sm tracking-widest uppercase hover:bg-white/10 transition-colors text-center flex items-center justify-center gap-2">
            View Full Schedule <ChevronRight className="w-4 h-4" />
          </Link>
        </motion.div>

        {/* Top Drivers */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="lg:col-span-1 glass-card p-8 flex flex-col gap-6"
        >
          <div className="flex justify-between items-center border-b border-white/10 pb-4">
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <Trophy className="w-5 h-5 text-f1-papaya" /> Defending Drivers
            </h3>
            <span className="text-xs font-bold text-f1-muted uppercase">2025 Top 3</span>
          </div>

          <div className="flex flex-col gap-4">
            {TOP_DRIVERS.map((driver, idx) => (
              <div key={idx} className="flex items-center gap-4 p-3 rounded-2xl bg-white/5 border border-white/5 hover:bg-white/10 transition-colors group">
                <div className="w-8 font-black text-2xl text-white/20 italic">
                  {idx + 1}
                </div>
                <div className="w-12 h-12 rounded-full overflow-hidden relative border-2 border-white/10 group-hover:scale-110 transition-transform bg-f1-navy">
                  <Image src={driver.img} alt={driver.name} fill className="object-cover object-top filter grayscale-[0.2] group-hover:grayscale-0" unoptimized />
                </div>
                <div className="flex flex-col flex-1 leading-tight">
                  <span className="text-white font-bold">{driver.name}</span>
                  <span className="text-xs font-semibold uppercase tracking-widest" style={{ color: driver.color }}>{driver.team}</span>
                </div>
                <div className="text-xl font-black text-white italic">
                  {driver.points} <span className="text-xs font-bold text-f1-muted uppercase not-italic">pts</span>
                </div>
              </div>
            ))}
          </div>

          <Link href="/standings" className="mt-auto w-full py-3 rounded-xl bg-white/5 border border-white/10 text-white font-bold text-sm tracking-widest uppercase hover:bg-white/10 transition-colors text-center flex items-center justify-center gap-2">
            Detailed Standings <ChevronRight className="w-4 h-4" />
          </Link>
        </motion.div>

        {/* Top Constructors */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="lg:col-span-1 glass-card p-8 flex flex-col gap-6"
        >
          <div className="flex justify-between items-center border-b border-white/10 pb-4">
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <Target className="w-5 h-5 text-f1-papaya" /> Constructors
            </h3>
            <span className="text-xs font-bold text-f1-muted uppercase">2025 Final</span>
          </div>

          <div className="flex flex-col gap-4">
            {TOP_CONSTRUCTORS.map((team, idx) => (
              <div key={idx} className="flex items-center gap-4 p-4 rounded-2xl bg-white/5 border-l-4 transition-all duration-300 hover:translate-x-1" style={{ borderLeftColor: team.color }}>
                <div className="w-12 h-12 relative flex items-center justify-center">
                  <Image src={team.logo} alt={team.name} fill className="object-contain" unoptimized />
                </div>
                <div className="flex flex-col flex-1 leading-tight">
                  <span className="text-white font-bold">{team.name}</span>
                </div>
                <div className="text-2xl font-black text-white italic">
                  {team.points} <span className="text-xs font-bold text-f1-muted uppercase not-italic">pts</span>
                </div>
              </div>
            ))}
          </div>

          <Link href="/teams" className="mt-auto w-full py-3 rounded-xl bg-white border border-white text-f1-navy font-black text-sm tracking-widest uppercase hover:bg-white/90 transition-colors text-center flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(255,255,255,0.2)]">
            Explore 2026 Grid <ChevronRight className="w-4 h-4" />
          </Link>
        </motion.div>

      </div>
    </div>
  );
}
