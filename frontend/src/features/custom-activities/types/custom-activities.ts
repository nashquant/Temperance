export interface CustomActivityRow {
  day_utc: string;
  line_no: number;
  activity: string;
  activity_text: string;
  duration_h: number;
  tss: number;
  rtss: number;
  distance_eqv_km: number;
  if_proxy_pct: number;
  pace_label: string;
  source: string;
}

export interface CustomActivityWeek {
  week_start: string;
  week_end: string;
  custom_activities: number;
  duration_h: number;
  tss: number;
  rtss: number;
  distance_eqv_km: number;
  if_proxy_pct: number;
}

export interface CustomActivitiesResponse {
  owner: string;
  rows: CustomActivityRow[];
  weeks: CustomActivityWeek[];
}

export interface CustomActivitiesIngestResponse {
  saved_count: number;
  errors: string[];
}
