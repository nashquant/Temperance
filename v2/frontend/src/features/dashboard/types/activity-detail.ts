export interface ActivityDetailLapRow {
  lapIndex: number;
  duration: number;
  elapsedDuration: number;
  distance: number;
  averageHR: number;
  maxHR: number;
  averageSpeed: number;
  calories: number;
}

export interface ActivityDetailResponse {
  owner: string;
  activity: {
    activity_id: string;
    date: string;
    start_time_utc: string;
    sport_type: string;
    distance_km: number;
    duration_min: number;
    avg_pace_display: string;
    avg_hr: number;
    max_hr: number;
    tss: number;
    rtss: number;
    training_load_garmin: number;
  };
  details: Record<string, unknown> & {
    source?: 'planned' | 'custom' | string;
  };
  raw?: {
    day_utc?: string;
    line_no?: number;
    workout_text?: string;
    activity_text?: string;
    [key: string]: unknown;
  };
  splits?: {
    lap_count?: number | null;
    total_duration_s?: number | null;
    total_distance_m?: number | null;
    split?: {
      lapDTOs?: ActivityDetailLapRow[];
      [key: string]: unknown;
    } | Record<string, unknown>;
    split_summaries?: {
      splitSummaries?: Array<Record<string, unknown>>;
      [key: string]: unknown;
    } | Record<string, unknown>;
  };
  split_rows?: Array<{
    lap: number;
    description: string;
    duration_label: string;
    duration_seconds?: number;
    avg_hr: number;
    if_pct: number;
    distance_km: number;
    distance_eqv_km: number;
    pace_label: string;
    pace_eqv_label: string;
    display_mode: 'running' | 'eqv';
  }>;
}
