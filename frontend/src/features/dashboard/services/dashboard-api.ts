import { API_CONFIG } from '@/api/config';
import { apiRequest } from '@/api/http-client';
import type { DashboardResponse } from '@/features/dashboard/types/dashboard';

interface GetDashboardParams {
  token: string;
  owner?: string;
  weeks: number;
  weekOffset?: number;
  sport?: string;
}

export async function getDashboard({ token, owner, weeks, weekOffset = 0, sport }: GetDashboardParams): Promise<DashboardResponse> {
  const search = new URLSearchParams({
    weeks: String(weeks),
  });
  if (weekOffset > 0) search.set('week_offset', String(weekOffset));
  if (owner) search.set('owner', owner);
  if (sport) search.set('sport', sport);

  return apiRequest<DashboardResponse>(`${API_CONFIG.endpoints.dashboard}?${search.toString()}`, {
    method: 'GET',
    token,
  });
}

