export interface DataExtractStatusResponse {
  owner: string;
  db_path: string;
  counts: Record<string, number>;
  last_sync: {
    sync_time_utc: string;
    source: string;
    success: boolean;
    message: string;
  } | null;
  garmin_credentials_available: boolean;
  garmin_credentials_source?: 'env' | 'session' | 'missing';
  garmin_runtime_credentials_set?: boolean;
  garmin_credentials_hint?: string;
  import_dir: string;
  extract_progress?: {
    running: boolean;
    phase: string | null;
    message: string | null;
    started_at: string | null;
    finished_at: string | null;
    updated_at: string | null;
    logs: string[];
    log_count: number;
    activities: {
      processed: number;
      total: number;
      day: string | null;
    };
    wellness: {
      current: number;
      total: number;
      day: string | null;
    };
  };
}

export interface SyncRequest {
  days_back: number;
  source: 'garmin_api' | 'file_import' | 'both';
  garmin_profile: 'quick' | 'deep';
}

export interface SyncResponse {
  success: boolean;
  messages: string[];
  total_rows: number;
  details: Record<string, unknown>;
}

export interface ComprehensiveExtractRequest {
  start_day: string;
  incremental_only: boolean;
  include_details: boolean;
  include_wellness: boolean;
  verify_raw_integrity: boolean;
}

export interface ComprehensiveExtractResponse {
  success: boolean;
  requested_start_day: string;
  computed_start_day: string;
  start_day: string;
  end_day: string;
  summary: string;
  errors: string[];
}

export interface GarminCredentialsRequest {
  email: string;
  password: string;
}

export interface GarminCredentialsResponse {
  updated: boolean;
  source: 'env' | 'session' | 'missing';
  message: string;
}
