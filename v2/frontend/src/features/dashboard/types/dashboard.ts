export interface DashboardZoneRow {
  zone: string;
  seconds: number;
  pct: number;
}

export interface DashboardWeekSummary {
  duration_h: number;
  distance_km: number;
  distance_eqv_km: number;
  calories: number;
  vdot_max: number | null;
  tss: number;
  rtss: number;
  fitness: number | null;
  fatigue: number | null;
  overreach: number | null;
  injury_risk: number | null;
  zones: DashboardZoneRow[];
}

export interface DashboardActivityCard {
  activity_id: string;
  sport: string;
  is_custom?: boolean;
  is_invalid?: boolean;
  day_utc?: string;
  line_no?: number;
  activity_text?: string;
  start_time_hhmm?: string;
  start_time_utc?: string;
  duration_label: string;
  distance_label: string;
  hr_label: string;
  pace_label: string;
  vdot?: number | null;
  if_pct: number;
  tss: number;
  rtss: number;
  intensity: 'green' | 'blue' | 'orange' | 'red' | string;
}

export interface DashboardPlannedCard {
  activity_id: string;
  day_utc: string;
  line_no: number;
  activity: string;
  workout_text: string;
  duration_label: string;
  distance_eqv_km: number;
  if_pct: number;
  pace_label: string;
  tss: number;
  rtss: number;
  manual_done: boolean;
  intensity: 'green' | 'blue' | 'orange' | 'red' | string;
}

export interface DashboardDayMeta {
  distance_eqv_km: number;
  calories: number;
  tss: number;
  fitness: number | null;
  fitness_expected: number | null;
  fatigue: number | null;
  fatigue_expected: number | null;
  resting_hr: number | null;
  hrv_status: number | null;
  stress_avg: number | null;
  planned_duration_s: number;
  planned_if_pct: number;
  show_fatigue_expected?: boolean;
}

export interface DashboardDayColumn {
  day_utc: string;
  day_label: string;
  is_today: boolean;
  is_past: boolean;
  meta: DashboardDayMeta;
  actual_activities: DashboardActivityCard[];
  planned_activities: DashboardPlannedCard[];
}

export interface DashboardWeekRow {
  week_start: string;
  week_end: string;
  week_number: number;
  summary: DashboardWeekSummary;
  days: DashboardDayColumn[];
}

export interface DashboardResponse {
  owner: string;
  db_path: string;
  weeks_total: number;
  weeks_visible: number;
  has_more_weeks: boolean;
  summary: {
    activities: number;
    distance_km: number;
    distance_eqv_km: number;
    tss: number;
    rtss: number;
  };
  weeks: DashboardWeekRow[];
}

export type DashboardSportFilter = 'all' | 'running' | 'treadmill' | 'cycling' | 'elliptical';
