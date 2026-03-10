import { useMemo, useRef, useState } from 'react';
import { Gauge, Moon, Sparkles, Target, Waves } from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import { intensityHexFromKey, intensityHexFromThreshold } from '@/features/dashboard/utils/intensity-palette';

type ActivitySplitsBarChartRow = {
  label: string;
  ifPct: number;
  type: string;
  duration_s: number;
  distanceLabel?: string;
  paceLabel?: string;
};

type ActivitySplitsBarChartProps = {
  data: ActivitySplitsBarChartRow[];
};

type ChartDatum = ActivitySplitsBarChartRow & {
  x0: number;
  x1: number;
  pctOfTotal: number;
  cumulativeDuration_s: number;
};

type TooltipState = {
  datum: ChartDatum;
  x: number;
  y: number;
} | null;

function getBarFill(type: string, ifPct: number): string {
  const normalizedType = String(type || '').trim().toLowerCase();

  if (
    normalizedType.includes('vo2') ||
    normalizedType.includes('v02') ||
    normalizedType.includes('vo2max') ||
    normalizedType.includes('anaerobic')
  ) {
    return intensityHexFromKey('purple');
  }
  if (normalizedType.includes('threshold') || normalizedType.includes('tempo hard') || normalizedType.includes('hard')) {
    return intensityHexFromKey('red');
  }
  if (normalizedType.includes('steady') || normalizedType.includes('tempo') || normalizedType.includes('mod')) {
    return intensityHexFromKey('orange');
  }
  if (normalizedType.includes('easy') || normalizedType.includes('endurance') || normalizedType.includes('aerobic')) {
    return intensityHexFromKey('blue');
  }
  if (normalizedType.includes('recovery') || normalizedType.includes('recover') || normalizedType.includes('rest')) {
    return intensityHexFromKey('green');
  }

  return intensityHexFromThreshold(ifPct);
}

function getTypeVisual(type: string, ifPct: number): {
  icon: typeof Moon;
  color: string;
} {
  const normalizedType = String(type || '').trim().toLowerCase();

  if (
    normalizedType.includes('vo2') ||
    normalizedType.includes('v02') ||
    normalizedType.includes('vo2max') ||
    normalizedType.includes('anaerobic')
  ) {
    return { icon: Sparkles, color: intensityHexFromKey('purple') };
  }
  if (normalizedType.includes('threshold') || normalizedType.includes('tempo hard') || normalizedType.includes('hard')) {
    return { icon: Target, color: intensityHexFromKey('red') };
  }
  if (normalizedType.includes('steady') || normalizedType.includes('tempo') || normalizedType.includes('mod')) {
    return { icon: Gauge, color: intensityHexFromKey('orange') };
  }
  if (normalizedType.includes('easy') || normalizedType.includes('endurance') || normalizedType.includes('aerobic')) {
    return { icon: Waves, color: intensityHexFromKey('blue') };
  }
  if (normalizedType.includes('recovery') || normalizedType.includes('recover') || normalizedType.includes('rest')) {
    return { icon: Moon, color: intensityHexFromKey('green') };
  }

  const fallbackColor = intensityHexFromThreshold(ifPct);
  if (fallbackColor === intensityHexFromKey('purple')) return { icon: Sparkles, color: fallbackColor };
  if (fallbackColor === intensityHexFromKey('red')) return { icon: Target, color: fallbackColor };
  if (fallbackColor === intensityHexFromKey('orange')) return { icon: Gauge, color: fallbackColor };
  if (fallbackColor === intensityHexFromKey('blue')) return { icon: Waves, color: fallbackColor };
  return { icon: Moon, color: fallbackColor };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  if (secs === 0) return `${minutes}'`;
  return `${minutes}'${String(secs).padStart(2, '0')}"`;
}

function formatElapsedTick(seconds: number): string {
  const roundedMinutes = Math.max(0, Math.round((Number(seconds) || 0) / 60));
  const hours = Math.floor(roundedMinutes / 60);
  const minutes = roundedMinutes % 60;

  if (hours > 0) {
    if (minutes === 0) return `${hours}h`;
    return `${hours}h ${minutes}'`;
  }
  return `${roundedMinutes}'`;
}

function buildElapsedTicks(totalSeconds: number, splitCount: number): Array<{ ratio: number; label: string }> {
  const total = Math.max(0, Number(totalSeconds) || 0);
  if (total <= 0) return [];

  const segmentCount = Math.max(1, Math.min(splitCount, total >= 45 * 60 ? 4 : total >= 20 * 60 ? 3 : 2));
  const ticks: Array<{ ratio: number; label: string }> = [];
  const seen = new Set<string>();

  for (let index = 1; index <= segmentCount; index += 1) {
    const ratio = index / segmentCount;
    const label = formatElapsedTick(total * ratio);
    if (seen.has(label)) continue;
    seen.add(label);
    ticks.push({ ratio, label });
  }

  return ticks;
}

function buildIfGuides(values: number[]): number[] {
  if (values.length === 0) return [];

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const span = Math.max(maxValue - minValue, 1);
  const roughStep = span / 2;

  let step = 5;
  if (roughStep > 25) step = 20;
  else if (roughStep > 12) step = 10;

  const start = Math.ceil(minValue / step) * step;
  const end = Math.floor(maxValue / step) * step;
  const guides: number[] = [];

  for (let current = start; current <= end; current += step) {
    if (current <= 0) continue;
    guides.push(current);
  }

  if (guides.length === 0) {
    const midpoint = Math.round(((minValue + maxValue) / 2) / step) * step;
    return midpoint > minValue && midpoint < maxValue ? [midpoint] : [];
  }

  if (guides.length <= 3) return guides;

  const picked = [guides[0], guides[Math.floor((guides.length - 1) / 2)], guides[guides.length - 1]];
  return [...new Set(picked)];
}
function buildChartData(data: ActivitySplitsBarChartRow[]): ChartDatum[] {
  const sanitized = data
    .map((row) => ({
      ...row,
      duration_s: Math.max(0, Number(row.duration_s) || 0),
      ifPct: Math.max(0, Number(row.ifPct) || 0),
      type: String(row.type || ''),
    }))
    .filter((row) => row.duration_s > 0);

  const totalDuration = sanitized.reduce((sum, row) => sum + row.duration_s, 0);
  let cumulative = 0;

  return sanitized.map((row) => {
    const x0 = totalDuration > 0 ? cumulative / totalDuration : 0;
    cumulative += row.duration_s;
    const x1 = totalDuration > 0 ? cumulative / totalDuration : 1;
    return {
      ...row,
      x0,
      x1,
      pctOfTotal: totalDuration > 0 ? row.duration_s / totalDuration : 0,
      cumulativeDuration_s: cumulative,
    };
  });
}

function ActivitySplitsBarTooltip({ tooltip }: { tooltip: TooltipState }): JSX.Element | null {
  if (!tooltip) return null;
  const { datum, x, y } = tooltip;
  const title = String(datum.type || datum.label || '-').trim() || '-';

  return (
    <div
      className="pointer-events-none absolute z-10 min-w-[120px] max-w-[150px] rounded-lg border border-sky-300/12 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.1),transparent_48%),linear-gradient(180deg,rgba(15,23,42,0.94),rgba(2,6,23,0.985))] px-2.5 py-2 text-[11px] shadow-[0_14px_28px_rgba(2,6,23,0.3)] backdrop-blur"
      style={{
        left: x,
        top: y,
        transform: 'translate(-50%, calc(-100% - 6px))',
      }}
    >
      <p className="mb-1.5 truncate text-[10px] font-semibold text-foreground">{title}</p>
      <div className="space-y-1 text-[9px]">
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-300/80">Duration</span>
          <span className="font-semibold text-foreground">{formatDuration(datum.duration_s)}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-300/80">Dist</span>
          <span className="font-semibold text-foreground">{datum.distanceLabel || '-'}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-300/80">Pace</span>
          <span className="font-semibold text-foreground">{datum.paceLabel || '-'}</span>
        </div>
      </div>
    </div>
  );
}

export function ActivitySplitsBarChart({ data }: ActivitySplitsBarChartProps): JSX.Element | null {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState>(null);
  const chartData = useMemo(() => buildChartData(data), [data]);

  if (chartData.length === 0) return null;

  const lapCount = chartData.length;
  const perLapWidth = 82;
  const minSvgWidth = 720;
  const sideMargin = Math.max(36, Math.min(150, 180 - lapCount * 11));
  const svgWidth = Math.max(minSvgWidth, lapCount * perLapWidth + sideMargin * 2);
  const svgHeight = 90;
  const margin = { top: 1, right: sideMargin, bottom: 5, left: sideMargin };
  const innerWidth = svgWidth - margin.left - margin.right;
  const innerHeight = svgHeight - margin.top - margin.bottom;
  const ifValues = chartData.map((row) => row.ifPct);
  const rawMinIf = Math.min(...ifValues);
  const rawMaxIf = Math.max(...ifValues);
  const yMin = Math.min(rawMinIf, 45);
  const yMax = Math.max(rawMaxIf, 100);
  const axisY = margin.top + innerHeight;
  const tickY = axisY + 14;
  const tickFontSize = 13;
  const totalDuration = chartData.at(-1)?.cumulativeDuration_s ?? 0;
  const elapsedTicks = buildElapsedTicks(totalDuration, chartData.length);

  return (
    <Card className="overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]">
      <CardContent className="px-3 py-2 sm:px-3.5 sm:py-2.5">
        <div className="mb-1 px-0.5">
          <p className="text-sm font-semibold text-foreground">Splits</p>
        </div>
        <div ref={containerRef} className="relative h-[102px] w-full" onMouseLeave={() => setTooltip(null)}>
          <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="h-full w-full" role="img" aria-label="Splits bar chart">
            {chartData.map((row) => {
              const x = margin.left + innerWidth * row.x0;
              const rawWidth = innerWidth * (row.x1 - row.x0);
              const width = Math.max(rawWidth - 4, 0);
              const barHeight = ((row.ifPct - yMin) / Math.max(yMax - yMin, 1)) * innerHeight;
              const y = axisY - barHeight;
              const active = tooltip?.datum.label === row.label;

              return (
                <g key={row.label}>
                  <rect
                    x={x}
                    y={y}
                    width={width}
                    height={barHeight}
                    rx="14"
                    fill={getBarFill(row.type, row.ifPct)}
                    opacity={1}
                    stroke={active ? 'rgba(226,232,240,0.9)' : 'rgba(255,255,255,0.08)'}
                    strokeWidth={active ? 1.5 : 1}
                    onMouseMove={(event) => {
                      const bounds = containerRef.current?.getBoundingClientRect();
                      if (!bounds) return;
                      setTooltip({
                        datum: row,
                        x: clamp(event.clientX - bounds.left, 90, bounds.width - 90),
                        y: clamp(event.clientY - bounds.top, 20, bounds.height - 20),
                      });
                    }}
                  />
                </g>
              );
            })}
            {elapsedTicks.map((tick) => {
              const x = margin.left + innerWidth * tick.ratio;
              return (
                <text
                  key={`${tick.ratio}-${tick.label}`}
                  x={x}
                  y={tickY}
                  fill="rgba(248,250,252,0.96)"
                  fontSize={tickFontSize}
                  fontWeight="700"
                  textAnchor={tick.ratio > 0.98 ? 'end' : 'middle'}
                >
                  {tick.label}
                </text>
              );
            })}
          </svg>
          <ActivitySplitsBarTooltip tooltip={tooltip} />
        </div>
      </CardContent>
    </Card>
  );
}
