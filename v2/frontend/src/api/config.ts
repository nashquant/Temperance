export const API_CONFIG = {
  basePath: '/api/v1',
  endpoints: {
    login: '/auth/login',
    me: '/auth/me',
    owners: '/auth/owners',
    dashboard: '/dashboard',
    wellness: '/wellness',
    activities: '/activities',
    athleteProgression: '/athlete-progression',
    settings: '/settings',
    vdot: '/vdot',
    dataExtractStatus: '/data-extract/status',
    dataExtractCredentials: '/data-extract/credentials',
    dataExtractSync: '/data-extract/sync',
    dataExtractComprehensive: '/data-extract/comprehensive',
    customActivities: '/custom-activities',
    customActivitiesIngest: '/custom-activities/ingest',
    customActivitiesWorkoutUpdate: '/custom-activities/workout',
    weekOutlook: '/week-outlook',
    plannedActivities: '/planned-activities',
    plannedManualDone: '/planned-activities/manual-done',
    plannedIngest: '/planned-activities/ingest',
    plannedWorkoutUpdate: '/planned-activities/workout',
  },
} as const;

// TODO: If your backend path changes (e.g., /v1 or another gateway prefix), update API_CONFIG.basePath.
// TODO: If auth token type changes from Bearer token, update header logic in src/api/http-client.ts.
