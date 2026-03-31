import { API_CONFIG } from '@/api/config';
import { apiRequest } from '@/api/http-client';
import type {
  CustomActivitiesIngestResponse,
  CustomActivitiesResponse,
} from '@/features/custom-activities/types/custom-activities';

interface BaseParams {
  token: string;
  owner?: string;
}

function withOwner(path: string, owner?: string): string {
  if (!owner) return path;
  const qs = new URLSearchParams({ owner });
  return `${path}?${qs.toString()}`;
}

export async function getCustomActivities({ token, owner }: BaseParams): Promise<CustomActivitiesResponse> {
  return apiRequest<CustomActivitiesResponse>(withOwner(API_CONFIG.endpoints.customActivities, owner), {
    method: 'GET',
    token,
  });
}

export async function ingestCustomActivities({ token, owner, entryText }: BaseParams & { entryText: string }): Promise<CustomActivitiesIngestResponse> {
  return apiRequest<CustomActivitiesIngestResponse>(withOwner(API_CONFIG.endpoints.customActivitiesIngest, owner), {
    method: 'POST',
    token,
    body: { entry_text: entryText },
  });
}

export async function updateCustomActivityWorkout(
  {
    token,
    owner,
    dayUtc,
    lineNo,
    activityText,
  }: BaseParams & { dayUtc: string; lineNo: number; activityText: string },
): Promise<{ updated: boolean }> {
  return apiRequest<{ updated: boolean }>(withOwner(API_CONFIG.endpoints.customActivitiesWorkoutUpdate, owner), {
    method: 'PATCH',
    token,
    body: {
      day_utc: dayUtc,
      line_no: lineNo,
      activity_text: activityText,
    },
  });
}

export async function deleteCustomActivity({ token, owner, dayUtc, lineNo }: BaseParams & { dayUtc: string; lineNo: number }): Promise<void> {
  const search = new URLSearchParams({
    day_utc: dayUtc,
    line_no: String(lineNo),
  });
  if (owner) search.set('owner', owner);

  await apiRequest<{ deleted: number }>(`${API_CONFIG.endpoints.customActivities}?${search.toString()}`, {
    method: 'DELETE',
    token,
  });
}
