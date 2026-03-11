import { API_CONFIG } from '@/api/config';
import { apiRequest } from '@/api/http-client';

interface GenerateActivityParams {
  token: string;
  owner?: string;
  dayUtc: string;
  mode: 'planned' | 'custom';
  activityType: 'running' | 'elliptical' | 'bike';
}

interface GenerateActivityResponse {
  owner: string;
  mode: 'planned' | 'custom';
  activity_text: string;
  total_candidates: number;
}

export async function generateActivitySuggestion({
  token,
  owner,
  dayUtc,
  mode,
  activityType,
}: GenerateActivityParams): Promise<GenerateActivityResponse> {
  const search = new URLSearchParams();
  if (owner) search.set('owner', owner);
  const suffix = search.toString().length > 0 ? `?${search.toString()}` : '';

  return apiRequest<GenerateActivityResponse>(`${API_CONFIG.endpoints.generatedActivity}${suffix}`, {
    method: 'POST',
    token,
    body: {
      day_utc: dayUtc,
      mode,
      activity_type: activityType,
    },
  });
}
