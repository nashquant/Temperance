export interface IfZoneThresholds {
  z1_max: number;
  z2_max: number;
  z3_max: number;
  z4_max: number;
}

export interface SpecificityProfile {
  non_running: number;
  treadmill: number;
  elliptical: number;
  cycling: number;
}

export interface BaselineBlendProfile {
  history_influence_pct: number;
  short_history_pct: number;
  medium_history_pct: number;
  long_history_pct: number;
}

export interface LthrCurvePoint {
  date: string;
  lthr_bpm: number;
}

export interface LtPaceCurvePoint {
  date: string;
  lt_pace_sec_per_km: number;
}

export interface InjuryWindow {
  label: string;
  start: string;
  end: string;
  severity: 'injury' | 'light_injury';
}

export interface VdotEquivalent {
  distance_m: number;
  time_min: number;
  time_hms: string;
  pace_sec_per_km: number;
  pace_label: string;
}

export interface VdotResponse {
  owner: string;
  as_of: string;
  vdot: number;
  threshold_assumption: {
    basis: string;
    equivalent_race_duration_min: number;
    lt_pace_sec_per_km: number;
    lt_pace_label: string;
  };
  equivalents: {
    '10k': VdotEquivalent;
    half_marathon: VdotEquivalent;
    marathon: VdotEquivalent;
  };
  observed_max?: {
    vdot: number;
    source_date: string;
    pred_lt_pace_sec_per_km: number;
    pred_lt_pace_label: string;
    equivalents: {
      '10k': VdotEquivalent;
      half_marathon: VdotEquivalent;
      marathon: VdotEquivalent;
    };
  } | null;
}

export interface SettingsResponse {
  owner: string;
  db_path: string;
  if_zone_thresholds: IfZoneThresholds;
  vdot_lookback_days: number;
  specificity_profile: SpecificityProfile;
  baseline_blend: BaselineBlendProfile;
  lthr_curve: LthrCurvePoint[];
  lt_pace_curve: LtPaceCurvePoint[];
  injury_windows: InjuryWindow[];
}

export interface UpdateSettingsRequest {
  if_zone_thresholds?: IfZoneThresholds;
  vdot_lookback_days?: number;
  specificity_profile?: SpecificityProfile;
  baseline_blend?: BaselineBlendProfile;
  lthr_curve?: LthrCurvePoint[];
  lt_pace_curve?: LtPaceCurvePoint[];
  injury_windows?: InjuryWindow[];
}
