import { API_CONFIG } from '@/api/config';
import { apiRequest } from '@/api/http-client';
import type { ActivityDetailResponse } from '@/features/dashboard/types/activity-detail';

interface GetActivityDetailParams {
  token: string;
  owner?: string;
  activityId: string;
}

export async function getActivityDetail({
  token,
  owner,
  activityId,
}: GetActivityDetailParams): Promise<ActivityDetailResponse> {
  const search = new URLSearchParams({
    include_records: 'false',
  });
  if (owner) search.set('owner', owner);
  return apiRequest<ActivityDetailResponse>(
    `${API_CONFIG.endpoints.activities}/${encodeURIComponent(activityId)}?${search.toString()}`,
    {
      method: 'GET',
      token,
    },
  );
}

