import {
  type WeeklyMetric,
  type WeeklyOutlookResponseRaw,
  type WeeklyOutlookViewModel,
} from '@/features/weekly-outlook/types/weekly-outlook';
import { formatDayLabel } from '@/features/weekly-outlook/utils/formatters';

function toMetric(rawMetric: WeeklyOutlookResponseRaw['metric']): WeeklyMetric {
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

  return {
    metric,
    compareLabel: toCompareLabel(raw.compare),
    weekStart: raw.week_start,
    weekEnd: raw.week_end,
    totals: {
      current: raw.week_total_current,
      compare: raw.week_total_compare,
      remainingToGo: raw.remaining_to_go,
      progressPct: raw.goal_progress_pct,
      projectedFinish: raw.projected_finish,
    },
    chartRows: raw.rows.map((row) => ({
      day: row.day,
      label: formatDayLabel(row.day),
      current: row.current,
      compare: row.compare,
      isToday: row.is_today,
      isFuture: row.is_future,
    })),
  };
}
