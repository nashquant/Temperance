export type ProgressionAggregation = "daily" | "weekly";
export type ProgressionActivityFilter =
  | "all"
  | "all_running"
  | "running"
  | "treadmill"
  | "cycling"
  | "elliptical";

export interface AthleteProgressionPoint {
  period_start: string;
  activities: number;
  distance_km: number;
  distance_eqv_km: number;
  duration_h: number;
  tss: number;
  rtss: number;
  calories_total: number;
  zone_low_aerobic_h: number;
  zone_moderate_aerobic_h: number;
  zone_high_aerobic_h: number;
  zone_total_h: number;
  performance_trend: number;
  performance_confidence: number;
  performance_efficiency: number;
  performance_threshold: number;
  performance_quality_confirmation: number;
  performance_durability_support: number;
  readiness: number;
  readiness_confidence: number;
  readiness_acute_strain: number;
  readiness_carryover_friction: number;
  readiness_recovery_response: number;
  tissue_load_risk: number;
  tissue_load_risk_confidence: number;
  tissue_run_ramp: number;
  tissue_single_run_spike: number;
  tissue_load_concentration: number;
  tissue_wellness_friction: number;
  durability: number;
  durability_confidence: number;
  durability_single_run_tolerance: number;
  durability_weekly_specific_tolerance: number;
  durability_specific_load_consistency: number;
  vdot: number | null;
  vdot_max: number | null;
  baseline_tss: number;
  baseline_rtss: number;
  baseline_distance_km: number;
  lt_target_tss: number;
  lt_target_distance_km: number;
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
