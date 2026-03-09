export type WellnessAggregation = 'daily' | 'weekly';

type WellnessMetric = number | null;

export interface WellnessPoint {
  period_start: string;
  sample_days: number;
  sleep_score: WellnessMetric;
  sleep_duration_h: WellnessMetric;
  deep_sleep_h: WellnessMetric;
  rem_sleep_h: WellnessMetric;
  light_sleep_h: WellnessMetric;
  awake_h: WellnessMetric;
  resting_hr: WellnessMetric;
  hrv_status: WellnessMetric;
  training_readiness: WellnessMetric;
  stress_avg: WellnessMetric;
  stress_max: WellnessMetric;
  body_battery_start: WellnessMetric;
  body_battery_end: WellnessMetric;
  body_battery_avg: WellnessMetric;
  respiration_avg: WellnessMetric;
  steps: WellnessMetric;
  intensity_minutes: WellnessMetric;
  calories_total: WellnessMetric;
}

export interface WellnessResponse {
  owner: string;
  db_path: string;
  days: number;
  aggregation: WellnessAggregation;
  range: {
    start_day: string;
    end_day: string;
  };
  summary: {
    latest_sleep_score: WellnessMetric;
    latest_resting_hr: WellnessMetric;
    latest_stress_avg: WellnessMetric;
    latest_training_readiness: WellnessMetric;
    latest_body_battery_end: WellnessMetric;
  };
  points: WellnessPoint[];
}
