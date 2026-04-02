import { Activity, AlertTriangle, Clock3, Flame, Gauge, Route, Ruler } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { formatCompactDurationHours } from '@/features/dashboard/utils/format-duration';
import { zoneHexFromLabel, zoneTrackClassNames, zoneTrackFallbackClassName } from '@/features/dashboard/utils/intensity-palette';
import type { DashboardWeekSummary } from '@/features/dashboard/types/dashboard';

interface DashboardWeekSummaryCardProps {
  weekNumber: number;
  weekStart: string;
  weekEnd: string;
  summary: DashboardWeekSummary;
  isCurrentWeek?: boolean;
}

function fmtNumber(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '-';
  return Math.round(value).toString();
}

function fmtSeconds(seconds: number): string {
  const totalMin = Math.max(0, Math.round(seconds / 60));
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h > 0) return m > 0 ? `${h}h${m}'` : `${h}h`;
  return `${m}'`;
}

const zoneColors: Record<string, string> = {
  Z1: zoneHexFromLabel('Z1'),
  Z2: zoneHexFromLabel('Z2'),
  Z3: zoneHexFromLabel('Z3'),
  Z4: zoneHexFromLabel('Z4'),
  Z5: zoneHexFromLabel('Z5'),
};


const summaryToneClassNames = {
  vdot: {
    label: 'text-sky-200/92',
    icon: 'text-sky-300/90',
    value: 'text-sky-100/92',
  },
  time: {
    label: 'text-cyan-200/92',
    icon: 'text-cyan-300/90',
    value: 'text-cyan-100/92',
  },
  distance: {
    label: 'text-emerald-200/92',
    icon: 'text-emerald-300/90',
    value: 'text-emerald-100/92',
  },
  equivalent: {
    label: 'text-lime-200/92',
    icon: 'text-lime-300/90',
    value: 'text-lime-100/92',
  },
  calories: {
    label: 'text-amber-200/92',
    icon: 'text-amber-300/90',
    value: 'text-amber-100/92',
  },
  stress: {
    label: 'text-blue-200/92',
    icon: 'text-blue-300/90',
    value: 'text-blue-100/92',
  },
  risk: {
    label: 'text-orange-200/92',
    icon: 'text-orange-300/90',
    value: 'text-orange-100/92',
  },
} as const;

export function DashboardWeekSummaryCard({ weekNumber, weekStart, weekEnd, summary, isCurrentWeek = false }: DashboardWeekSummaryCardProps): JSX.Element {
  return (
    <Card className="rounded-xl border-border/80 bg-card/80 shadow-sm lg:h-[430px]">
      <CardContent className="flex h-full flex-col space-y-3 overflow-y-auto p-2.5">
        <div className="space-y-1">
          <Badge
            variant="outline"
            className={`h-5 rounded-full px-2 text-[10px] font-semibold tracking-wide ${
              isCurrentWeek
                ? 'border-sky-300/45 bg-sky-300/12 text-sky-100 shadow-[0_0_0_1px_rgba(125,211,252,0.12),0_4px_14px_rgba(14,165,233,0.12)]'
                : ''
            }`}
          >
            Week {weekNumber}
          </Badge>
          <p className="text-[13px] font-medium leading-5 text-muted-foreground">
            {weekStart} - {weekEnd}
          </p>
        </div>

        <div className="grid grid-cols-[1fr_auto] gap-x-1.5 gap-y-1">
          <p className={`inline-flex items-center gap-1 text-[11.5px] font-medium leading-[1.28] tracking-[0.01em] ${summaryToneClassNames.vdot.label}`}>
            <Gauge className={`h-3 w-3 ${summaryToneClassNames.vdot.icon}`} />
            VDOT Max
          </p>
          <p className={`text-right text-[11px] font-semibold tabular-nums ${summaryToneClassNames.vdot.value}`}>{fmtNumber(summary.vdot_max)}</p>
          <p className={`inline-flex items-center gap-1 text-[11.5px] font-medium leading-[1.28] tracking-[0.01em] ${summaryToneClassNames.time.label}`}><Clock3 className={`h-3 w-3 ${summaryToneClassNames.time.icon}`} />Time</p>
          <p className={`text-right text-[11px] font-medium tabular-nums ${summaryToneClassNames.time.value}`}>{formatCompactDurationHours(summary.duration_h)}</p>
          <p className={`inline-flex items-center gap-1 text-[11.5px] font-medium leading-[1.28] tracking-[0.01em] ${summaryToneClassNames.distance.label}`}><Route className={`h-3 w-3 ${summaryToneClassNames.distance.icon}`} />Dist</p>
          <p className={`text-right text-[11px] font-medium tabular-nums ${summaryToneClassNames.distance.value}`}>{fmtNumber(summary.distance_km)} km</p>
          <p className={`inline-flex items-center gap-1 text-[11.5px] font-medium leading-[1.28] tracking-[0.01em] ${summaryToneClassNames.equivalent.label}`}><Ruler className={`h-3 w-3 ${summaryToneClassNames.equivalent.icon}`} />Eqv</p>
          <p className={`text-right text-[11px] font-medium tabular-nums ${summaryToneClassNames.equivalent.value}`}>{fmtNumber(summary.distance_eqv_km)} km</p>
          <p className={`inline-flex items-center gap-1 text-[11.5px] font-medium leading-[1.28] tracking-[0.01em] ${summaryToneClassNames.calories.label}`}><Flame className={`h-3 w-3 ${summaryToneClassNames.calories.icon}`} />kcal</p>
          <p className={`text-right text-[11px] font-medium tabular-nums ${summaryToneClassNames.calories.value}`}>{fmtNumber(summary.calories)}</p>
          <p className={`inline-flex items-center gap-1 text-[11.5px] font-medium leading-[1.28] tracking-[0.01em] ${summaryToneClassNames.stress.label}`}><Activity className={`h-3 w-3 ${summaryToneClassNames.stress.icon}`} />TSS | rTSS</p>
          <p className={`text-right text-[11px] font-medium tabular-nums ${summaryToneClassNames.stress.value}`}>{fmtNumber(summary.tss)} | {fmtNumber(summary.rtss)}</p>
          <p className={`inline-flex items-center gap-1 text-[11.5px] font-medium leading-[1.28] tracking-[0.01em] ${summaryToneClassNames.risk.label}`}><AlertTriangle className={`h-3 w-3 ${summaryToneClassNames.risk.icon}`} />Ovr | Risk</p>
          <p className={`text-right text-[11px] font-medium tabular-nums ${summaryToneClassNames.risk.value}`}>{fmtNumber(summary.overreach)} | {fmtNumber(summary.injury_risk)}</p>
        </div>

        <Separator className="bg-border/70" />

        <div className="space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Zones</p>
          {summary.zones.map((zone) => (
            <div key={zone.zone} className="grid grid-cols-[32px_minmax(36px,1fr)_42px_24px] items-center gap-1 text-[11px] leading-4 text-muted-foreground">
              <span className="inline-flex items-center gap-1 text-[11.5px] font-medium leading-[1.28] tracking-[0.01em] text-slate-200/92">
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: zoneColors[zone.zone] ?? zoneHexFromLabel('Z1') }}
                />
                {zone.zone}
              </span>
              <div
                className={`h-1.5 w-full overflow-hidden rounded-full border ${zoneTrackClassNames[zone.zone] ?? zoneTrackFallbackClassName}`}
              >
                <div
                  className="h-full rounded-full"
                  style={{
                    backgroundColor: zoneColors[zone.zone] ?? zoneHexFromLabel('Z1'),
                    width: `${zone.pct > 0 ? Math.max(3, Math.min(100, zone.pct)) : 0}%`,
                  }}
                />
              </div>
              <span className="text-right font-medium tabular-nums text-slate-200/92">{fmtSeconds(zone.seconds)}</span>
              <span className="text-right">{zone.pct.toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
