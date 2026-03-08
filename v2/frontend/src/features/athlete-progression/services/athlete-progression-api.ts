import { API_CONFIG } from '@/api/config';
import { apiRequest } from '@/api/http-client';
import type {
  AthleteProgressionResponse,
  ProgressionActivityFilter,
  ProgressionAggregation,
} from '@/features/athlete-progression/types/athlete-progression';

interface Params {
  token: string;
  owner?: string;
  days: number;
  aggregation: ProgressionAggregation;
  activityFilter: ProgressionActivityFilter;
}

export async function getAthleteProgression({
  token,
  owner,
  days,
  aggregation,
  activityFilter,
}: Params): Promise<AthleteProgressionResponse> {
  const search = new URLSearchParams({
    days: String(days),
    aggregation,
    activity_filter: activityFilter,
  });
  if (owner) search.set('owner', owner);

  return apiRequest<AthleteProgressionResponse>(`${API_CONFIG.endpoints.athleteProgression}?${search.toString()}`, {
    method: 'GET',
    token,
  });
}
