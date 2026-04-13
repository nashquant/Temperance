import { API_CONFIG } from '@/api/config';
import { apiRequest } from '@/api/http-client';

interface ActivityMergeParams {
  token: string;
  owner?: string;
}

interface CreateActivityMergeRequest {
  activity_ids: string[];
}

interface CreateActivityMergeResponse {
  merge_id: number;
}

export async function createActivityMerge(
  { token, owner }: ActivityMergeParams,
  activityIds: string[],
): Promise<CreateActivityMergeResponse> {
  const search = new URLSearchParams();
  if (owner) search.set('owner', owner);
  const suffix = search.toString() ? `?${search.toString()}` : '';

  const payload: CreateActivityMergeRequest = {
    activity_ids: activityIds,
  };

  return apiRequest<CreateActivityMergeResponse>(`${API_CONFIG.endpoints.activityMerges}${suffix}`, {
    method: 'POST',
    token,
    body: payload,
  });
}

export async function deleteActivityMerge(
  { token, owner }: ActivityMergeParams,
  mergeId: number,
): Promise<void> {
  const search = new URLSearchParams();
  if (owner) search.set('owner', owner);
  const suffix = search.toString() ? `?${search.toString()}` : '';

  return apiRequest<void>(`${API_CONFIG.endpoints.activityMerges}/${mergeId}${suffix}`, {
    method: 'DELETE',
    token,
  });
}
