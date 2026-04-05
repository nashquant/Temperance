export type PlannedMetricView = 'tss' | 'rtss' | 'distance_eqv_km';

export interface PlannedWeekSummary {
  week_start: string;
  week_end: string;
  week_label: string;
  goal_tss: number;
  goal_rtss: number;
  goal_distance_eqv_km: number;
  planned_activities: number;
  duration_h: number;
  tss: number;
  rtss: number;
  distance_eqv_km: number;
  if_proxy_pct: number;
}

export interface PlannedActivityRow {
  day_utc: string;
  line_no: number;
  activity: string;
  workout_text: string;
  manual_done: boolean;
  tss: number;
  rtss: number;
  distance_eqv_km: number;
  duration_h: number;
  if_proxy_pct: number;
}

export interface PlannedActivitiesResponse {
  owner: string;
  db_path: string;
  goals: {
    tss: number;
    rtss: number;
    distance_eqv_km: number;
  };
  weeks: PlannedWeekSummary[];
  rows: PlannedActivityRow[];
}
