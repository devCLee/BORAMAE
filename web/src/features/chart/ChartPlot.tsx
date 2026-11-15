"use client";

import { cn } from "cn";
import { area, extent, line, scaleLinear } from "d3";
import { useLocale } from "next-intl";
import {
  type RefObject,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

import { formatNumber } from "@/lib/format";

import type { BandPoint, ChartForm, ChartPoint } from "./chart-forms";

// ponytail: plot size, margins and tick spacing are working values; no document sets a
// chart size (TRD Q-24). The width follows the container, from this first guess.
const DEFAULT_WIDTH = 640;
const HEIGHT = 260;
const MARGIN = { top: 24, right: 16, bottom: 28, left: 52 };
const PIXELS_PER_YEAR_TICK = 80;
const MIN_YEAR_TICKS = 2;
const VALUE_TICKS = 5;
const POINT_RADIUS = 3.5;
const TICK_GAP = 6;
const YEAR_LABEL_OFFSET = 18;
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";
// ponytail: the series fades and slides in from the left (tw-animate-css). A stroke
// reveal needs keyframes in globals.css. No document gives a duration or easing.
const DRAW_IN = "animate-in fade-in slide-in-from-left-4 duration-700";

/** The utility classes of the design role that the trend line and the band take. */
export interface TrendRole {
  line: string;
  band: string;
}

interface ChartPlotProps {
  points: ChartPoint[];
  form: ChartForm;
  trendLine: ChartPoint[] | null;
  band: BandPoint[] | null;
  role: TrendRole;
  unitLabel: string;
  labelledBy: string;
  describedBy: string;
}

/** The SVG of the chart. D3 gives scales and paths only, and React renders every element. */
export function ChartPlot({
  points,
  form,
  trendLine,
  band,
  role,
  unitLabel,
  labelledBy,
  describedBy,
}: ChartPlotProps) {
  const locale = useLocale();
  const containerRef = useRef<HTMLDivElement>(null);
  const width = useWidth(containerRef);
  const isMotionReduced = useIsMotionReduced();

  const x = scaleLinear()
    .domain(toDomain(points.map((point) => point.x)))
    .range([MARGIN.left, width - MARGIN.right]);
  const y = scaleLinear()
    .domain(
      toDomain([
        ...points.map((point) => point.y),
        ...(trendLine ?? []).map((point) => point.y),
        ...(band ?? []).flatMap((corner) => [corner.y0, corner.y1]),
      ]),
    )
    .nice(VALUE_TICKS)
    .range([HEIGHT - MARGIN.bottom, MARGIN.top]);
  const toPath = line<ChartPoint>()
    .defined((point) => point.y !== null)
    .x((point) => x(point.x))
    .y((point) => y(point.y ?? Number.NaN));
  const toArea = area<BandPoint>()
    .x((corner) => x(corner.x))
    .y0((corner) => y(corner.y0))
    .y1((corner) => y(corner.y1));
  const yearTicks = x
    .ticks(
      Math.max(
        MIN_YEAR_TICKS,
        Math.floor((width - MARGIN.left - MARGIN.right) / PIXELS_PER_YEAR_TICK),
      ),
    )
    .filter(Number.isInteger);

  return (
    <div ref={containerRef} className="w-full overflow-hidden">
      <svg
        role="img"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        width={width}
        height={HEIGHT}
        className="block text-xs"
      >
        <text x={MARGIN.left} y={MARGIN.top / 2} className="fill-muted-foreground">
          {unitLabel}
        </text>
        {y.ticks(VALUE_TICKS).map((tick) => (
          <g key={tick}>
            <line
              x1={MARGIN.left}
              x2={width - MARGIN.right}
              y1={y(tick)}
              y2={y(tick)}
              className="stroke-border"
            />
            <text
              x={MARGIN.left - TICK_GAP}
              y={y(tick)}
              dy="0.32em"
              textAnchor="end"
              className="fill-muted-foreground"
            >
              {formatNumber(tick, locale)}
            </text>
          </g>
        ))}
        {yearTicks.map((tick) => (
          <text
            key={tick}
            x={x(tick)}
            y={HEIGHT - MARGIN.bottom + YEAR_LABEL_OFFSET}
            textAnchor="middle"
            className="fill-muted-foreground"
          >
            {tick}
          </text>
        ))}
        <g data-testid="chart-series" className={cn(!isMotionReduced && DRAW_IN)}>
          {band && (
            <path
              data-testid="chart-band"
              d={toArea(band) ?? undefined}
              className={role.band}
            />
          )}
          {form === "yearly" ? (
            points.map((point) => (
              <circle
                key={point.x}
                data-testid="chart-point"
                cx={x(point.x)}
                cy={y(point.y ?? Number.NaN)}
                r={POINT_RADIUS}
                className={
                  point.isCensored
                    ? "fill-background stroke-foreground stroke-[1.5]"
                    : "fill-foreground"
                }
              />
            ))
          ) : (
            <path
              data-testid="chart-monthly-line"
              d={toPath(points) ?? undefined}
              className="fill-none stroke-foreground"
            />
          )}
          {trendLine && (
            <path
              data-testid="chart-trend-line"
              d={toPath(trendLine) ?? undefined}
              className={cn("fill-none stroke-2", role.line)}
            />
          )}
        </g>
      </svg>
    </div>
  );
}

/** The extent of the values. A constant series gets one unit on each side, so it draws as a flat row. */
function toDomain(values: (number | null)[]): [number, number] {
  const [low = 0, high = 0] = extent(values, (value) => value);
  return low === high ? [low - 1, high + 1] : [low, high];
}

function useWidth(ref: RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  useEffect(() => {
    const element = ref.current;
    if (element === null) {
      return;
    }
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0) {
        setWidth(entry.contentRect.width);
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}

function useIsMotionReduced(): boolean {
  return useSyncExternalStore(
    subscribeToMotion,
    () => window.matchMedia(REDUCED_MOTION_QUERY).matches,
    // The static build draws no motion.
    () => true,
  );
}

function subscribeToMotion(onChange: () => void): () => void {
  const query = window.matchMedia(REDUCED_MOTION_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}
