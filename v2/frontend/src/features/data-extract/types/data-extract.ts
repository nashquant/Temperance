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
  import_dir: string;
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
  start_day: string;
  end_day: string;
  summary: string;
  errors: string[];
}
