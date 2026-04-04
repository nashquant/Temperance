import { Activity, AlertTriangle, Clock3, Flame, Gauge, Route, Ruler } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { ZoneBar } from '@/features/dashboard/components/zone-bar';
import { formatCompactDurationHours } from '@/features/dashboard/utils/format-duration';
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

const summaryRowClassNames = {
  icon: 'h-3 w-3 lg:h-3.5 lg:w-3.5',
  label: 'text-[10.5px] font-medium leading-[1.2] tracking-[0.01em] lg:text-[12px] lg:leading-[1.32]',
  value: 'text-[10.5px] tabular-nums lg:text-[11.5px]',
  zoneLabel: 'text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground lg:text-[11px]',
} as const;


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
    <Card className="rounded-xl border-border/80 bg-card/80 shadow-sm md:h-[418px] lg:h-[442px]">
      <CardContent className="flex h-full flex-col space-y-2 overflow-y-auto p-2 md:p-2.5 lg:space-y-3 lg:p-3">
        <div className="space-y-0.5">
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
          <p className="text-[12px] font-medium leading-4.5 text-muted-foreground md:text-[11.5px] lg:text-[13.5px]">
            {weekStart} - {weekEnd}
          </p>
        </div>

        <div className="grid grid-cols-[1fr_auto] gap-x-1 gap-y-0.5">
          <p className={`inline-flex items-center gap-1 ${summaryRowClassNames.label} ${summaryToneClassNames.vdot.label}`}>
            <Gauge className={`${summaryRowClassNames.icon} ${summaryToneClassNames.vdot.icon}`} />
            VDOT
          </p>
          <p className={`text-right ${summaryRowClassNames.value} font-semibold ${summaryToneClassNames.vdot.value}`}>{fmtNumber(summary.vdot_max)}</p>
          <p className={`inline-flex items-center gap-1 ${summaryRowClassNames.label} ${summaryToneClassNames.time.label}`}><Clock3 className={`${summaryRowClassNames.icon} ${summaryToneClassNames.time.icon}`} />Time</p>
          <p className={`text-right ${summaryRowClassNames.value} font-medium ${summaryToneClassNames.time.value}`}>{formatCompactDurationHours(summary.duration_h)}</p>
          <p className={`inline-flex items-center gap-1 ${summaryRowClassNames.label} ${summaryToneClassNames.distance.label}`}><Route className={`${summaryRowClassNames.icon} ${summaryToneClassNames.distance.icon}`} />Dist</p>
          <p className={`text-right ${summaryRowClassNames.value} font-medium ${summaryToneClassNames.distance.value}`}>{fmtNumber(summary.distance_km)} km</p>
          <p className={`inline-flex items-center gap-1 ${summaryRowClassNames.label} ${summaryToneClassNames.equivalent.label}`}><Ruler className={`${summaryRowClassNames.icon} ${summaryToneClassNames.equivalent.icon}`} />Eqv</p>
          <p className={`text-right ${summaryRowClassNames.value} font-medium ${summaryToneClassNames.equivalent.value}`}>{fmtNumber(summary.distance_eqv_km)} km</p>
          <p className={`inline-flex items-center gap-1 ${summaryRowClassNames.label} ${summaryToneClassNames.calories.label}`}><Flame className={`${summaryRowClassNames.icon} ${summaryToneClassNames.calories.icon}`} />kcal</p>
          <p className={`text-right ${summaryRowClassNames.value} font-medium ${summaryToneClassNames.calories.value}`}>{fmtNumber(summary.calories)}</p>
          <p className={`inline-flex items-center gap-1 ${summaryRowClassNames.label} ${summaryToneClassNames.stress.label}`}><Activity className={`${summaryRowClassNames.icon} ${summaryToneClassNames.stress.icon}`} />TSS|rTSS</p>
          <p className={`text-right ${summaryRowClassNames.value} font-medium ${summaryToneClassNames.stress.value}`}>{fmtNumber(summary.tss)} | {fmtNumber(summary.rtss)}</p>
          <p className={`inline-flex items-center gap-1 ${summaryRowClassNames.label} ${summaryToneClassNames.risk.label}`}><AlertTriangle className={`${summaryRowClassNames.icon} ${summaryToneClassNames.risk.icon}`} />Ovr|Risk</p>
          <p className={`text-right ${summaryRowClassNames.value} font-medium ${summaryToneClassNames.risk.value}`}>{fmtNumber(summary.overreach)} | {fmtNumber(summary.injury_risk)}</p>
        </div>

        <Separator className="bg-border/70" />

        <div className="space-y-0.5">
          <p className={summaryRowClassNames.zoneLabel}>Zones</p>
          {summary.zones.map((zone) => (
            <ZoneBar key={zone.zone} zone={zone.zone} seconds={zone.seconds} pct={zone.pct} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
