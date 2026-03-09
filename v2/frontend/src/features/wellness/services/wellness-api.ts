import { API_CONFIG } from '@/api/config';
import { apiRequest } from '@/api/http-client';
import type { WellnessAggregation, WellnessResponse } from '@/features/wellness/types';

interface Params {
  token: string;
  owner?: string;
  days: number;
  aggregation: WellnessAggregation;
}

export async function getWellness({ token, owner, days, aggregation }: Params): Promise<WellnessResponse> {
  const search = new URLSearchParams({
    days: String(days),
    aggregation,
  });
  if (owner) search.set('owner', owner);

  return apiRequest<WellnessResponse>(`${API_CONFIG.endpoints.wellness}?${search.toString()}`, {
    method: 'GET',
    token,
  });
}
