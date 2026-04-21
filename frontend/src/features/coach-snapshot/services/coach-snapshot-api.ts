import { API_CONFIG } from '@/api/config';
import { apiRequest } from '@/api/http-client';
import type { CoachSnapshotResponse } from '@/features/coach-snapshot/types/coach-snapshot';

interface CoachSnapshotParams {
  token: string;
  owner?: string;
}

export async function getCoachSnapshot({ token, owner }: CoachSnapshotParams): Promise<CoachSnapshotResponse> {
  const search = new URLSearchParams();
  if (owner) search.set('owner', owner);
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return apiRequest<CoachSnapshotResponse>(`${API_CONFIG.endpoints.coachSnapshot}${suffix}`, {
    method: 'GET',
    token,
  });
}
