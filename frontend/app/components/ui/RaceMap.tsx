"use client";

import React, {
    useCallback,
    useEffect,
    useId,
    useMemo,
    useRef,
    useState,
} from "react";
import { Mercator, Graticule } from "@visx/geo";
import { Zoom } from "@visx/zoom";
import type { ProvidedZoom, TransformMatrix, ZoomState } from "@visx/zoom";
import { RectClipPath } from "@visx/clip-path";
import type { Feature, Geometry } from "geojson";
import * as topojson from "topojson-client";
import { Minus, Plus, Crosshair } from "lucide-react";

/**
 * Container size, from a ResizeObserver plus one synchronous read on
 * attach.
 *
 * This is deliberately not `react-use-measure` — under React 19 its
 * observer never fired for this element and the map sat at 0×0 forever,
 * stuck on its loading state. The synchronous first read also means the
 * expanded map has real dimensions on its very first paint instead of
 * waiting a frame for the observer, which is the difference between the
 * zoom animation starting with a map in it and starting empty.
 *
 * Sizes come from offsetWidth/offsetHeight, never getBoundingClientRect:
 * the expanded panel spends its opening animation under a CSS scale, and
 * a rect-based read would hand the map the *scaled* size — reprojecting
 * the whole world at the wrong size, then again when the transform lands.
 */
function useElementSize<T extends HTMLElement>() {
    const [size, setSize] = useState({ width: 0, height: 0 });
    const cleanup = useRef<(() => void) | null>(null);

    const ref = useCallback((node: T | null) => {
        cleanup.current?.();
        cleanup.current = null;
        if (!node) return;

        const read = () => {
            const width = node.offsetWidth;
            const height = node.offsetHeight;
            setSize((prev) =>
                prev.width === width && prev.height === height
                    ? prev
                    : { width, height }
            );
        };

        read();
        const observer = new ResizeObserver(read);
        observer.observe(node);
        cleanup.current = () => observer.disconnect();
    }, []);

    useEffect(() => () => cleanup.current?.(), []);

    return [ref, size] as const;
}

/* ═══════════════════════════════════════════════════════════════════════
   TYPES
   ═══════════════════════════════════════════════════════════════════════ */

export type RaceMapStatus = "next" | "completed" | "upcoming";

export type RaceMapLocation = {
    slug: string;
    /** Circuit name — "Circuit de Monaco". */
    name: string;
    /** City/locality — "Monte Carlo". */
    locality: string;
    lat: number;
    long: number;
    round?: number;
    /** ISO date from the season schedule. */
    date?: string;
    status: RaceMapStatus;
    /** One extra line for the tooltip (e.g. backtest accuracy for a past round). */
    note?: string;
};

export type RaceMapProps = {
    locations: RaceMapLocation[];
    selectedSlug?: string | null;
    onSelect?: (location: RaceMapLocation | null) => void;
    /** Wheel zoom, drag pan, marker/region hit testing. Off for the preview. */
    zoomEnabled?: boolean;
    zoomMin?: number;
    zoomMax?: number;
    initialZoom?: number;
    /** Duration in ms of the programmatic fly-to / zoom-button tweens. */
    animationDuration?: number;
    /** [longitude, latitude] the projection is centred on. */
    center?: [number, number];
    /** Pixel offset of that centre. Defaults to the middle of the canvas. */
    translate?: [number, number];
    /**
     * Width of a panel covering the left of the map. Fly-to and the zoom
     * buttons centre on what's still visible beside it, so a circuit the
     * user just clicked doesn't land underneath the dossier.
     */
    focusInsetLeft?: number;
    showControls?: boolean;
    showLegend?: boolean;
    showTooltips?: boolean;
    className?: string;
};

/* ═══════════════════════════════════════════════════════════════════════
   WORLD TOPOLOGY

   Module-scoped so the preview and the expanded view — two live instances
   of this component at once — share one fetch and one decode, and so the
   expanded map paints its first frame with geometry already in hand
   instead of flashing a loading state in the middle of the zoom.
   ═══════════════════════════════════════════════════════════════════════ */

type WorldFeature = Feature<Geometry, { name?: string }>;
type World = { type: "FeatureCollection"; features: WorldFeature[] };

/** The zoom API @visx/zoom hands to its render prop. */
type ZoomApi<E extends Element> = ProvidedZoom<E> & ZoomState;

let worldCache: World | null = null;
let worldRequest: Promise<World> | null = null;

function loadWorld(): Promise<World> {
    if (worldCache) return Promise.resolve(worldCache);
    if (!worldRequest) {
        worldRequest = fetch("/data/world-topology.json")
            .then((res) => res.json())
            .then((topology) => {
                const collection = topojson.feature(
                    topology,
                    topology.objects.countries
                ) as unknown as World;
                worldCache = collection;
                return collection;
            })
            .catch((err) => {
                // Let a later mount retry rather than caching the failure.
                worldRequest = null;
                throw err;
            });
    }
    return worldRequest;
}

/* ═══════════════════════════════════════════════════════════════════════
   MARKER TREATMENT

   Three states only. "next" is the round the Predictions page is actually
   about, so it gets the accent and the pulse; everything else stays a
   quiet status dot.
   ═══════════════════════════════════════════════════════════════════════ */

const STATUS_COLOR: Record<RaceMapStatus, string> = {
    next: "var(--color-accent-hot)",
    completed: "var(--color-good)",
    upcoming: "var(--color-warn)",
};

const STATUS_LABEL: Record<RaceMapStatus, string> = {
    next: "Next round",
    completed: "Raced",
    upcoming: "Upcoming",
};

const MONTH_DAY = (iso?: string) =>
    iso
        ? new Date(iso).toLocaleDateString("en-GB", {
              day: "numeric",
              month: "short",
          })
        : null;

/* ═══════════════════════════════════════════════════════════════════════
   COMPONENT
   ═══════════════════════════════════════════════════════════════════════ */

export default function RaceMap({
    locations,
    selectedSlug = null,
    onSelect,
    zoomEnabled = true,
    zoomMin = 0.8,
    zoomMax = 14,
    initialZoom = 1,
    animationDuration = 650,
    center = [0, 12],
    translate,
    focusInsetLeft = 0,
    showControls = true,
    showLegend = true,
    showTooltips = true,
    className = "",
}: RaceMapProps) {
    const [ref, size] = useElementSize<HTMLDivElement>();
    const [world, setWorld] = useState<World | null>(worldCache);

    // Rounded so sub-pixel resize noise doesn't churn the projection.
    const width = Math.round(size.width);
    const height = Math.round(size.height);
    const measured = width > 0 && height > 0;

    useEffect(() => {
        if (worldCache) return;
        let alive = true;
        loadWorld()
            .then((collection) => {
                if (alive) setWorld(collection);
            })
            .catch((err) => console.error("World topology load failed:", err));
        return () => {
            alive = false;
        };
    }, []);

    // Fit the full 360° of longitude to the container, falling back to the
    // height when the container is narrow enough that latitude binds first.
    // 2.7 projection units is roughly ±60° of latitude, which comfortably
    // covers the calendar (Melbourne at -37.8 up to Zandvoort at 52.4).
    const projectionScale = useMemo(
        () => Math.min(width / (2 * Math.PI), height / 2.7) * 0.98,
        [width, height]
    );

    const initialTransformMatrix = useMemo<TransformMatrix>(
        () => ({
            scaleX: initialZoom,
            scaleY: initialZoom,
            translateX: (width / 2) * (1 - initialZoom),
            translateY: (height / 2) * (1 - initialZoom),
            skewX: 0,
            skewY: 0,
        }),
        [width, height, initialZoom]
    );

    return (
        <div
            ref={ref}
            className={`relative w-full h-full overflow-hidden bg-ink-2 ${className}`}
        >
            {world && measured ? (
                <Zoom<SVGSVGElement>
                    // Zoom seeds its matrix from initialTransformMatrix once;
                    // remounting on resize is what keeps the view centred
                    // when the map grows from preview to expanded.
                    key={`${width}x${height}`}
                    width={width}
                    height={height}
                    scaleXMin={zoomMin}
                    scaleXMax={zoomMax}
                    scaleYMin={zoomMin}
                    scaleYMax={zoomMax}
                    initialTransformMatrix={initialTransformMatrix}
                >
                    {(zoom) => (
                        <MapSurface
                            zoom={zoom}
                            world={world}
                            width={width}
                            height={height}
                            projectionScale={projectionScale}
                            projectionCenter={center}
                            projectionTranslate={
                                translate ?? [width / 2, height / 2]
                            }
                            locations={locations}
                            selectedSlug={selectedSlug}
                            onSelect={onSelect}
                            zoomEnabled={zoomEnabled}
                            focusInsetLeft={focusInsetLeft}
                            animationDuration={animationDuration}
                            showControls={showControls && zoomEnabled}
                            showLegend={showLegend}
                            showTooltips={showTooltips && zoomEnabled}
                        />
                    )}
                </Zoom>
            ) : (
                <div className="absolute inset-0 grid place-items-center">
                    <span className="label-xs animate-pulse">Loading circuits</span>
                </div>
            )}
        </div>
    );
}

/* ═══════════════════════════════════════════════════════════════════════
   SURFACE

   Split out of RaceMap because @visx/zoom hands the zoom API to a render
   prop — the hooks that depend on it (the fly-to tween, its cleanup) need
   a real component to live in.
   ═══════════════════════════════════════════════════════════════════════ */

type SurfaceProps = {
    zoom: ZoomApi<SVGSVGElement>;
    world: World;
    width: number;
    height: number;
    projectionScale: number;
    projectionCenter: [number, number];
    projectionTranslate: [number, number];
    locations: RaceMapLocation[];
    selectedSlug: string | null;
    onSelect?: (location: RaceMapLocation | null) => void;
    zoomEnabled: boolean;
    focusInsetLeft: number;
    animationDuration: number;
    showControls: boolean;
    showLegend: boolean;
    showTooltips: boolean;
};

type Hovered =
    | { kind: "location"; location: RaceMapLocation; x: number; y: number }
    | { kind: "region"; name: string; x: number; y: number };

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const easeInOutCubic = (t: number) =>
    t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

function MapSurface({
    zoom,
    world,
    width,
    height,
    projectionScale,
    projectionCenter,
    projectionTranslate,
    locations,
    selectedSlug,
    onSelect,
    zoomEnabled,
    focusInsetLeft,
    animationDuration,
    showControls,
    showLegend,
    showTooltips,
}: SurfaceProps) {
    const clipId = useId();
    const [hovered, setHovered] = useState<Hovered | null>(null);

    // The zoom API is a fresh object on every render; holding it in a ref
    // keeps the tween callbacks stable instead of re-creating them on each
    // of the frames they themselves cause.
    const zoomRef = useRef(zoom);
    zoomRef.current = zoom;

    const frame = useRef<number | null>(null);
    const cancelTween = useCallback(() => {
        if (frame.current !== null) {
            cancelAnimationFrame(frame.current);
            frame.current = null;
        }
    }, []);
    useEffect(() => cancelTween, [cancelTween]);

    const tweenTo = useCallback(
        (target: TransformMatrix) => {
            cancelTween();
            const from = zoomRef.current.transformMatrix;
            const reduced =
                typeof window !== "undefined" &&
                window.matchMedia("(prefers-reduced-motion: reduce)").matches;

            if (animationDuration <= 0 || reduced) {
                zoomRef.current.setTransformMatrix(target);
                return;
            }

            const start = performance.now();
            const step = (now: number) => {
                const t = Math.min(1, (now - start) / animationDuration);
                const e = easeInOutCubic(t);
                zoomRef.current.setTransformMatrix({
                    scaleX: lerp(from.scaleX, target.scaleX, e),
                    scaleY: lerp(from.scaleY, target.scaleY, e),
                    translateX: lerp(from.translateX, target.translateX, e),
                    translateY: lerp(from.translateY, target.translateY, e),
                    skewX: 0,
                    skewY: 0,
                });
                frame.current = t < 1 ? requestAnimationFrame(step) : null;
            };
            frame.current = requestAnimationFrame(step);
        },
        [animationDuration, cancelTween]
    );

    // The middle of the map the user can actually see — the dossier panel
    // covers the left of the canvas when one is open.
    const focusX = (focusInsetLeft + width) / 2;

    /** Zoom to `scale`, keeping the given projection-space point centred. */
    const flyTo = useCallback(
        (point: { x: number; y: number }, scale: number) =>
            tweenTo({
                scaleX: scale,
                scaleY: scale,
                translateX: focusX - point.x * scale,
                translateY: height / 2 - point.y * scale,
                skewX: 0,
                skewY: 0,
            }),
        [tweenTo, focusX, height]
    );

    /** Zoom about the centre of the visible map by a multiplier. */
    const zoomBy = useCallback(
        (factor: number) => {
            const m = zoomRef.current.transformMatrix;
            const next = m.scaleX * factor;
            // Whatever sits at that centre stays there.
            const cx = (focusX - m.translateX) / m.scaleX;
            const cy = (height / 2 - m.translateY) / m.scaleY;
            tweenTo({
                scaleX: next,
                scaleY: next,
                translateX: focusX - cx * next,
                translateY: height / 2 - cy * next,
                skewX: 0,
                skewY: 0,
            });
        },
        [tweenTo, focusX, height]
    );

    const resetView = useCallback(() => {
        onSelect?.(null);
        tweenTo(zoomRef.current.initialTransformMatrix);
    }, [onSelect, tweenTo]);

    /* ── Fly to the selected circuit ──────────────────────────────────
       Driven by the selection rather than by the click that caused it:
       the same click also opens the dossier, and only after that state
       has landed does `focusInsetLeft` — and so the centre to fly to —
       account for the panel about to cover the left of the map.

       Marker positions are cached during render (below) because the
       projection only exists inside the Mercator render prop. */
    const markerPoints = useRef<Record<string, [number, number]>>({});
    const flownTo = useRef<string | null>(null);

    useEffect(() => {
        if (!zoomEnabled) return;
        if (!selectedSlug) {
            flownTo.current = null;
            return;
        }
        if (flownTo.current === selectedSlug) return;
        const point = markerPoints.current[selectedSlug];
        if (!point) return;
        flownTo.current = selectedSlug;
        flyTo({ x: point[0], y: point[1] }, 5);
    }, [selectedSlug, zoomEnabled, flyTo]);

    const scale = zoom.transformMatrix.scaleX;

    /* Tooltip placement — flips to the other side of the cursor near the
       container edges so it never spills out of the map. */
    const tooltipStyle = useMemo(() => {
        if (!hovered) return undefined;
        const flipX = hovered.x > width - 200;
        const flipY = hovered.y < 90;
        return {
            left: hovered.x,
            top: hovered.y,
            transform: `translate(${flipX ? "-100%" : "0"}, ${
                flipY ? "12px" : "calc(-100% - 12px)"
            }) translateX(${flipX ? "-10px" : "10px"})`,
        } as React.CSSProperties;
    }, [hovered, width]);

    return (
        <div className="relative w-full h-full">
            <svg
                width={width}
                height={height}
                className={`absolute inset-0 ${
                    zoomEnabled
                        ? zoom.isDragging
                            ? "cursor-grabbing"
                            : "cursor-grab"
                        : "pointer-events-none"
                }`}
                onMouseDown={
                    zoomEnabled
                        ? (e) => {
                              cancelTween();
                              zoom.dragStart(e);
                          }
                        : undefined
                }
                onMouseMove={zoomEnabled ? zoom.dragMove : undefined}
                onMouseUp={zoomEnabled ? zoom.dragEnd : undefined}
                onMouseLeave={
                    zoomEnabled
                        ? () => {
                              zoom.dragEnd();
                              setHovered(null);
                          }
                        : undefined
                }
                onWheel={
                    zoomEnabled
                        ? (e) => {
                              cancelTween();
                              zoom.handleWheel(e);
                          }
                        : undefined
                }
            >
                <RectClipPath id={clipId} width={width} height={height} />

                <g clipPath={`url(#${clipId})`}>
                    {/* Ocean plane, and the click target that clears a
                        selection — markers stop propagation before this. */}
                    <rect
                        width={width}
                        height={height}
                        fill="var(--color-ink-2)"
                        onClick={zoomEnabled ? () => onSelect?.(null) : undefined}
                    />

                    <g transform={zoom.toString()}>
                        <Mercator
                            data={world.features}
                            scale={projectionScale}
                            translate={projectionTranslate}
                            center={projectionCenter}
                        >
                            {(mercator) => (
                                <g>
                                    <Graticule
                                        graticule={(g) => mercator.path(g) || ""}
                                        stroke="rgba(255,255,255,0.04)"
                                        strokeWidth={0.5 / scale}
                                    />

                                    {/* Regions. The hover fill is CSS rather
                                        than React state — re-rendering 177
                                        paths on every pointer move is a
                                        stutter you can feel. */}
                                    <g
                                        onClick={
                                            zoomEnabled
                                                ? () => onSelect?.(null)
                                                : undefined
                                        }
                                        onMouseMove={
                                            showTooltips
                                                ? (e) => {
                                                      const name = (
                                                          e.target as SVGElement
                                                      ).dataset?.region;
                                                      if (!name) return;
                                                      setHovered((prev) =>
                                                          prev?.kind === "location"
                                                              ? prev
                                                              : {
                                                                    kind: "region",
                                                                    name,
                                                                    x: e.nativeEvent.offsetX,
                                                                    y: e.nativeEvent.offsetY,
                                                                }
                                                      );
                                                  }
                                                : undefined
                                        }
                                    >
                                        {mercator.features.map(({ feature, path }, i) => (
                                            <path
                                                key={`region-${i}`}
                                                className="race-map-region"
                                                data-region={feature.properties?.name ?? ""}
                                                d={path || ""}
                                                strokeWidth={0.5 / scale}
                                            />
                                        ))}
                                    </g>

                                    {/* Race markers, above the regions and
                                        counter-scaled so they hold the same
                                        size on screen at every zoom level. */}
                                    {locations.map((location) => {
                                        const point = mercator.projection([
                                            location.long,
                                            location.lat,
                                        ]);
                                        if (!point) return null;
                                        const [cx, cy] = point;
                                        // Cache for the fly-to effect above.
                                        markerPoints.current[location.slug] = [cx, cy];
                                        const isSelected = selectedSlug === location.slug;
                                        const color = STATUS_COLOR[location.status];

                                        return (
                                            <g
                                                key={location.slug}
                                                transform={`translate(${cx}, ${cy}) scale(${
                                                    1 / scale
                                                })`}
                                                className={
                                                    zoomEnabled ? "cursor-pointer" : undefined
                                                }
                                                onClick={
                                                    zoomEnabled
                                                        ? (e) => {
                                                              e.stopPropagation();
                                                              onSelect?.(location);
                                                          }
                                                        : undefined
                                                }
                                                onMouseEnter={
                                                    showTooltips
                                                        ? (e) =>
                                                              setHovered({
                                                                  kind: "location",
                                                                  location,
                                                                  x: e.nativeEvent.offsetX,
                                                                  y: e.nativeEvent.offsetY,
                                                              })
                                                        : undefined
                                                }
                                                onMouseLeave={
                                                    showTooltips
                                                        ? () => setHovered(null)
                                                        : undefined
                                                }
                                            >
                                                {/* Generous invisible hit area —
                                                    a 4px dot is not a target. */}
                                                {zoomEnabled && (
                                                    <circle r={12} fill="transparent" />
                                                )}

                                                {/* The ping. Two rings offset in
                                                    time on the next round so it
                                                    reads as a beacon; a single
                                                    ring on a selected marker. */}
                                                {location.status === "next" ? (
                                                    <>
                                                        <circle
                                                            className="race-marker-ping"
                                                            r={5}
                                                            fill="none"
                                                            stroke={color}
                                                            strokeWidth={1.5}
                                                        />
                                                        <circle
                                                            className="race-marker-ping race-marker-ping--delayed"
                                                            r={5}
                                                            fill="none"
                                                            stroke={color}
                                                            strokeWidth={1.5}
                                                        />
                                                        <circle
                                                            className="race-marker-glow"
                                                            r={9}
                                                            fill={color}
                                                        />
                                                    </>
                                                ) : (
                                                    isSelected && (
                                                        <circle
                                                            className="race-marker-ping"
                                                            r={5}
                                                            fill="none"
                                                            stroke={color}
                                                            strokeWidth={1.5}
                                                        />
                                                    )
                                                )}

                                                {isSelected && (
                                                    <circle
                                                        r={10}
                                                        fill="none"
                                                        stroke={color}
                                                        strokeWidth={1}
                                                        opacity={0.7}
                                                    />
                                                )}

                                                <circle
                                                    r={location.status === "next" ? 4.5 : 3.5}
                                                    fill={color}
                                                    stroke="var(--color-ink-0)"
                                                    strokeWidth={1.25}
                                                    style={{
                                                        filter: `drop-shadow(0 0 6px ${color})`,
                                                    }}
                                                />
                                            </g>
                                        );
                                    })}
                                </g>
                            )}
                        </Mercator>
                    </g>
                </g>
            </svg>

            {/* ── Tooltip ──────────────────────────────────────────── */}
            {showTooltips && hovered && (
                <div
                    className="absolute z-20 pointer-events-none max-w-[220px]
                               rounded-[var(--radius-chip)] border border-line-strong
                               bg-ink-1/95 backdrop-blur-md px-3 py-2 shadow-2xl"
                    style={tooltipStyle}
                >
                    {hovered.kind === "location" ? (
                        <>
                            <p className="text-[13px] font-bold text-fg leading-tight">
                                {hovered.location.locality}
                            </p>
                            <p className="text-[11px] text-fg-muted leading-snug mt-0.5">
                                {hovered.location.name}
                            </p>
                            <p className="label-xs mt-1.5 flex items-center gap-1.5">
                                <span
                                    className="w-1.5 h-1.5 rounded-full inline-block"
                                    style={{
                                        backgroundColor:
                                            STATUS_COLOR[hovered.location.status],
                                    }}
                                />
                                {hovered.location.round != null &&
                                    `R${hovered.location.round} · `}
                                {STATUS_LABEL[hovered.location.status]}
                                {MONTH_DAY(hovered.location.date) &&
                                    ` · ${MONTH_DAY(hovered.location.date)}`}
                            </p>
                            {hovered.location.note && (
                                <p className="text-[11px] text-fg-subtle mt-1">
                                    {hovered.location.note}
                                </p>
                            )}
                        </>
                    ) : (
                        <p className="text-[12px] font-semibold text-fg-muted">
                            {hovered.name}
                        </p>
                    )}
                </div>
            )}

            {/* ── Legend ───────────────────────────────────────────── */}
            {showLegend && (
                <div
                    className="absolute top-3 left-3 z-10 flex flex-wrap gap-x-3 gap-y-1.5
                               rounded-[var(--radius-chip)] border border-line
                               bg-ink-1/80 backdrop-blur-md px-2.5 py-2 pointer-events-none"
                >
                    {(["next", "upcoming", "completed"] as RaceMapStatus[]).map(
                        (status) => (
                            <span key={status} className="flex items-center gap-1.5">
                                <span
                                    className="w-2 h-2 rounded-full"
                                    style={{
                                        backgroundColor: STATUS_COLOR[status],
                                        boxShadow: `0 0 8px ${STATUS_COLOR[status]}`,
                                    }}
                                />
                                <span className="label-xs">{STATUS_LABEL[status]}</span>
                            </span>
                        )
                    )}
                </div>
            )}

            {/* ── Zoom controls ────────────────────────────────────── */}
            {showControls && (
                <div className="absolute bottom-3 right-3 z-10 flex items-center gap-1.5">
                    <MapButton label="Zoom out" onClick={() => zoomBy(1 / 1.6)}>
                        <Minus className="w-4 h-4" />
                    </MapButton>
                    <MapButton label="Zoom in" onClick={() => zoomBy(1.6)}>
                        <Plus className="w-4 h-4" />
                    </MapButton>
                    <MapButton label="Reset view" onClick={resetView}>
                        <Crosshair className="w-4 h-4" />
                    </MapButton>
                </div>
            )}
        </div>
    );
}

function MapButton({
    label,
    onClick,
    children,
}: {
    label: string;
    onClick: () => void;
    children: React.ReactNode;
}) {
    return (
        <button
            type="button"
            aria-label={label}
            title={label}
            onClick={onClick}
            className="grid place-items-center w-8 h-8 rounded-[var(--radius-chip)]
                       border border-line bg-ink-1/85 backdrop-blur-md
                       text-fg-muted hover:text-fg hover:bg-ink-3
                       transition-colors"
        >
            {children}
        </button>
    );
}
