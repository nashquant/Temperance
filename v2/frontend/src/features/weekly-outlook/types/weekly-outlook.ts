export type WeeklyMetric = 'tss' | 'distance';

export interface WeeklyOutlookRowRaw {
  day: string;
  day_label?: string;
  current: number;
  compare: number;
  is_today: boolean;
  is_future: boolean;
}

export interface WeeklyOutlookResponseRaw {
  metric: 'tss' | 'rtss' | 'distance_eqv_km';
  compare: 'planned' | 'previous_week' | 'two_weeks_ago' | 'three_weeks_ago' | 'four_weeks_ago';
  week_start: string;
  week_end: string;
  compare_week_start: string;
  compare_week_end: string;
  goal: number;
  goal_progress_pct: number;
  wtd_current: number;
  wtd_compare: number;
  remaining_to_go: number;
  projected_finish: number | null;
  estimated_fatigue_eow: number | null;
  week_total_current: number;
  week_total_compare: number;
  rows: WeeklyOutlookRowRaw[];
  today_day: string;
}

export interface WeeklyChartRow {
  day: string;
  label: string;
  current: number;
  compare: number;
  isToday: boolean;
  isFuture: boolean;
}

export interface WeeklyOutlookViewModel {
  metric: WeeklyMetric;
  compareLabel: string;
  chartRows: WeeklyChartRow[];
  weekStart: string;
  weekEnd: string;
  totals: {
    current: number;
    compare: number;
    remainingToGo: number;
    progressPct: number;
    projectedFinish: number | null;
  };
}
