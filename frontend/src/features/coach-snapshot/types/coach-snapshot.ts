export type PhaseProgressStatus = 'on_phase_track' | 'ahead_phase_load' | 'behind_phase_load';

export interface CoachSnapshotResponse {
  owner: string;
  db_path: string;
  current_phase: string | null;
  next_phase: string | null;
  next_race_date: string | null;
  next_race_type: string | null;
  days_to_race: number | null;
  weekly_total_tss_target: number;
  weekly_rtss_target: number;
  phase_progress_pct: number;
  phase_progress_status: PhaseProgressStatus | string;
  generated_at_utc: string;
}
