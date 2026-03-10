export type ProgressionAggregation = 'daily' | 'weekly';
export type ProgressionActivityFilter = 'all' | 'all_running' | 'running' | 'treadmill' | 'cycling' | 'elliptical';

export interface AthleteProgressionPoint {
  period_start: string;
  activities: number;
  distance_km: number;
  distance_eqv_km: number;
  duration_h: number;
  tss: number;
  rtss: number;
  training_load_garmin: number;
  calories_total: number;
  zone_low_aerobic_h: number;
  zone_moderate_aerobic_h: number;
  zone_high_aerobic_h: number;
  zone_total_h: number;
  fitness: number;
  fatigue: number;
  overreach: number;
  injury_risk: number;
  leg_elasticity: number;
  pounding: number;
  vdot: number | null;
  vdot_max: number | null;
  target_tss: number;
  target_distance_km: number;
}

export interface AthleteProgressionResponse {
  owner: string;
  db_path: string;
  days: number;
  activity_filter: string;
  aggregation: ProgressionAggregation;
  range: {
    start_day: string;
    end_day: string;
  };
  summary: {
    activities: number;
    distance_km: number;
    distance_eqv_km: number;
    tss: number;
    rtss: number;
  };
  points: AthleteProgressionPoint[];
  vdot_eligibility?: {
    running_like_activities: number;
    running_like_with_distance_duration: number;
    eligible_candidates_before_vdot: number;
    eligible_candidates_after_vdot: number;
    max_single_activity_if_pct: number;
    max_single_activity_rtss: number;
  };
}
