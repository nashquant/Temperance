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

export interface SettingsResponse {
  owner: string;
  db_path: string;
  if_zone_thresholds: IfZoneThresholds;
  specificity_profile: SpecificityProfile;
  lthr_curve: LthrCurvePoint[];
  lt_pace_curve: LtPaceCurvePoint[];
  injury_windows: InjuryWindow[];
}

export interface UpdateSettingsRequest {
  if_zone_thresholds?: IfZoneThresholds;
  specificity_profile?: SpecificityProfile;
  lthr_curve?: LthrCurvePoint[];
  lt_pace_curve?: LtPaceCurvePoint[];
  injury_windows?: InjuryWindow[];
}
