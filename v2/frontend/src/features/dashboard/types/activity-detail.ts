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
  details: Record<string, unknown>;
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
}

