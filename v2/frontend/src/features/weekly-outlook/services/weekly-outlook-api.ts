import { API_CONFIG } from '@/api/config';
import { apiRequest } from '@/api/http-client';
import type { WeeklyCompare, WeeklyMetric, WeeklyOutlookResponseRaw } from '@/features/weekly-outlook/types/weekly-outlook';

interface WeeklyOutlookParams {
  token: string;
  owner?: string;
  metric: WeeklyMetric;
  compare?: WeeklyCompare;
}

function metricToApi(metric: WeeklyMetric): 'tss' | 'rtss' | 'distance_eqv_km' {
  if (metric === 'distance') return 'distance_eqv_km';
  if (metric === 'rtss') return 'rtss';
  return 'tss';
}

export async function getWeeklyOutlook({
  token,
  owner,
  metric,
  compare = 'planned',
}: WeeklyOutlookParams): Promise<WeeklyOutlookResponseRaw> {
  const search = new URLSearchParams({
    metric: metricToApi(metric),
    compare,
  });

  if (owner) {
    search.set('owner', owner);
  }

  return apiRequest<WeeklyOutlookResponseRaw>(`${API_CONFIG.endpoints.weekOutlook}?${search.toString()}`, {
    method: 'GET',
    token,
  });
}

// TODO: If backend requires additional filters (e.g. week_start, sport, days), add them here.
