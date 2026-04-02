import {
  type WeeklyMetric,
  type WeeklyOutlookResponseRaw,
  type WeeklyOutlookViewModel,
} from '@/features/weekly-outlook/types/weekly-outlook';
import { formatDayLabel } from '@/features/weekly-outlook/utils/formatters';

function toMetric(rawMetric: WeeklyOutlookResponseRaw['metric']): WeeklyMetric {
  if (rawMetric === 'rtss') return 'rtss';
  return rawMetric === 'distance_eqv_km' ? 'distance' : 'tss';
}

function toCompareLabel(rawCompare: WeeklyOutlookResponseRaw['compare']): string {
  if (rawCompare === 'planned') return 'Planned week';
  if (rawCompare === 'previous_week') return 'Previous week';
  if (rawCompare === 'two_weeks_ago') return 'Two weeks ago';
  if (rawCompare === 'three_weeks_ago') return 'Three weeks ago';
  return 'Four weeks ago';
}

export function mapWeeklyOutlookResponse(raw: WeeklyOutlookResponseRaw): WeeklyOutlookViewModel {
  const metric = toMetric(raw.metric);
  const comparisonTotal = raw.compare === 'planned' ? raw.wtd_compare : raw.week_total_compare;
  const progressPct =
    raw.compare === 'planned' && (raw.projected_finish ?? 0) > 0
      ? Math.round((raw.week_total_current / raw.projected_finish!) * 100)
      : raw.goal_progress_pct;

  return {
    metric,
    compare: raw.compare,
    compareLabel: toCompareLabel(raw.compare),
    compareWeekStart: raw.compare_week_start,
    compareWeekEnd: raw.compare_week_end,
    weekStart: raw.week_start,
    weekEnd: raw.week_end,
    totals: {
      current: raw.week_total_current,
      compare: comparisonTotal,
      remainingToGo: raw.remaining_to_go,
      progressPct,
      projectedFinish: raw.projected_finish,
      estimatedFatigueEow: raw.estimated_fatigue_eow,
    },
    chartRows: raw.rows.map((row) => ({
      day: row.day,
      label: formatDayLabel(row.day),
      current: row.current,
      compare: row.compare,
      currentTss: row.current_tss ?? (metric === 'tss' ? row.current : 0),
      isToday: row.is_today,
      isFuture: row.is_future,
    })),
  };
}
