import { API_CONFIG } from '@/api/config';
import { apiRequest } from '@/api/http-client';

interface ActivityMergeParams {
  token: string;
  owner?: string;
}

interface CreateActivityMergeRequest {
  activity_id_1: string;
  activity_id_2: string;
}

interface CreateActivityMergeResponse {
  merge_id: number;
}

export async function createActivityMerge(
  { token, owner }: ActivityMergeParams,
  activityId1: string,
  activityId2: string,
): Promise<CreateActivityMergeResponse> {
  const search = new URLSearchParams();
  if (owner) search.set('owner', owner);
  const suffix = search.toString() ? `?${search.toString()}` : '';

  const payload: CreateActivityMergeRequest = {
    activity_id_1: activityId1,
    activity_id_2: activityId2,
  };

  return apiRequest<CreateActivityMergeResponse>(`/activity-merges${suffix}`, {
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

  return apiRequest<void>(`/activity-merges/${mergeId}${suffix}`, {
    method: 'DELETE',
    token,
  });
}
