"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Fluid Glass Surface — ported from akhil-portfolio/components/GlassSurface.tsx
 *
 * Builds an SVG displacement map for a refraction pass that makes the dock
 * read as thick frosted glass rather than a flat blurred panel.
 *
 * feDisplacementMap reads the X offset from the red channel and Y from green,
 * where 128 means "no shift". The two gradients are screen-blended so the
 * middle of the surface lands on rgb(128,128,·) — flat — while the outer
 * bands ramp toward 0/255 (the rim-only falloff that sells "glass thickness").
 *
 * Drop this as the first child of a `relative rounded-*` container and wrap
 * the container's real content in `relative z-10`.
 */

const buildDisplacementMap = (xBand: number, yBand: number) =>
    "data:image/svg+xml;utf8," +
    encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200" preserveAspectRatio="none">` +
        `<defs>` +
        `<linearGradient id="x" x1="0" y1="0" x2="1" y2="0">` +
        `<stop offset="0%" stop-color="#000000"/>` +
        `<stop offset="${xBand}%" stop-color="#800000"/>` +
        `<stop offset="${100 - xBand}%" stop-color="#800000"/>` +
        `<stop offset="100%" stop-color="#ff0000"/>` +
        `</linearGradient>` +
        `<linearGradient id="y" x1="0" y1="0" x2="0" y2="1">` +
        `<stop offset="0%" stop-color="#000000"/>` +
        `<stop offset="${yBand}%" stop-color="#008000"/>` +
        `<stop offset="${100 - yBand}%" stop-color="#008000"/>` +
        `<stop offset="100%" stop-color="#00ff00"/>` +
        `</linearGradient>` +
        `</defs>` +
        `<rect width="200" height="200" fill="url(#x)"/>` +
        `<rect width="200" height="200" fill="url(#y)" style="mix-blend-mode:screen"/>` +
        `</svg>`
    );

const FILTER_ID = "f1-liquid-glass-refraction";
const BAND_PX = 28;
const DISPLACEMENT_SCALE = 72; // Significantly higher for dense, liquid-like distortion

export default function GlassSurface({ rounded = "rounded-[20px]" }: { rounded?: string }) {
    const surfaceRef = useRef<HTMLDivElement>(null);
    const sheenRef = useRef<HTMLDivElement>(null);
    const [canRefract, setCanRefract] = useState(false);
    const [bands, setBands] = useState({ x: 30, y: 9 });

    // Progressive enhancement: check if browser supports url() in backdrop-filter
    useEffect(() => {
        setCanRefract(
            typeof CSS !== "undefined" &&
            typeof CSS.supports === "function" &&
            CSS.supports("backdrop-filter", `url(#${FILTER_ID})`)
        );
    }, []);

    // Keep the rim a constant physical width regardless of dock dimensions
    useEffect(() => {
        const el = surfaceRef.current;
        if (!el) return;
        const observer = new ResizeObserver(([entry]) => {
            const { width, height } = entry.contentRect;
            if (!width || !height) return;
            setBands({
                x: Math.min(45, (BAND_PX / width) * 100),
                y: Math.min(45, (BAND_PX / height) * 100),
            });
        });
        observer.observe(el);
        return () => observer.disconnect();
    }, []);

    // Pointer-tracked specular highlight — written to CSS custom properties
    // and rAF-throttled so cursor drags never re-render React.
    useEffect(() => {
        let frame = 0;
        let pending: PointerEvent | null = null;

        const apply = () => {
            frame = 0;
            const surface = surfaceRef.current;
            const sheen = sheenRef.current;
            if (!pending || !surface || !sheen) return;
            const rect = surface.getBoundingClientRect();
            if (!rect.width || !rect.height) return;
            const x = ((pending.clientX - rect.left) / rect.width) * 100;
            const y = ((pending.clientY - rect.top) / rect.height) * 100;
            sheen.style.setProperty("--spec-x", `${x}%`);
            sheen.style.setProperty("--spec-y", `${y}%`);
        };

        const onMove = (event: PointerEvent) => {
            pending = event;
            if (!frame) frame = requestAnimationFrame(apply);
        };

        window.addEventListener("pointermove", onMove, { passive: true });
        return () => {
            window.removeEventListener("pointermove", onMove);
            if (frame) cancelAnimationFrame(frame);
        };
    }, []);

    const backdrop = canRefract
        ? `blur(2.5px) url(#${FILTER_ID}) saturate(1.6) brightness(1.15)`
        : "blur(20px) saturate(1.5) brightness(1.1)";

    return (
        <>
            <svg aria-hidden className="absolute w-0 h-0 pointer-events-none">
                <filter
                    id={FILTER_ID}
                    x="-25%"
                    y="-25%"
                    width="150%"
                    height="150%"
                    colorInterpolationFilters="sRGB"
                >
                    <feImage
                        href={buildDisplacementMap(bands.x, bands.y)}
                        result="map"
                        preserveAspectRatio="none"
                    />
                    <feGaussianBlur in="map" stdDeviation="2" result="smoothMap" />
                    <feDisplacementMap
                        in="SourceGraphic"
                        in2="smoothMap"
                        scale={DISPLACEMENT_SCALE}
                        xChannelSelector="R"
                        yChannelSelector="G"
                    />
                </filter>
            </svg>

            {/* Refraction pass — bends whatever is behind the dock */}
            <div
                ref={surfaceRef}
                aria-hidden
                className={`absolute inset-0 ${rounded} pointer-events-none`}
                style={{ backdropFilter: backdrop, WebkitBackdropFilter: backdrop }}
            />

            {/* Tint, rim light and pointer-tracked specular */}
            <div
                ref={sheenRef}
                aria-hidden
                className={`absolute inset-0 ${rounded} pointer-events-none`}
                style={{
                    ["--spec-x" as string]: "50%",
                    ["--spec-y" as string]: "0%",
                    background: [
                        "rgba(12, 12, 16, 0.45)", // Base dark tint replacing the one removed from .dock
                        "radial-gradient(140px circle at var(--spec-x) var(--spec-y), rgba(255,255,255,0.18), rgba(255,255,255,0) 70%)",
                        "linear-gradient(160deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.03) 30%, rgba(255,255,255,0) 50%, rgba(255,255,255,0.06) 100%)",
                    ].join(", "),
                    boxShadow: [
                        "inset 0 1px 1.5px rgba(255,255,255,0.4)",
                        "inset 0 -1px 1px rgba(255,255,255,0.1)",
                        "inset 1px 0 1px rgba(255,255,255,0.15)",
                        "inset -1px 0 1px rgba(255,255,255,0.15)",
                    ].join(", "),
                }}
            />
        </>
    );
}
