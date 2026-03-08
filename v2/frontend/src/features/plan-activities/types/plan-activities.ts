export type PlannedMetricView = 'tss' | 'rtss' | 'distance_eqv_km' | 'if_proxy_pct';

export interface PlannedWeekSummary {
  week_start: string;
  week_end: string;
  week_label: string;
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
