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

export async function deleteCustomActivity({ token, owner, dayUtc, lineNo }: BaseParams & { dayUtc: string; lineNo: number }): Promise<void> {
  const url = new URL(`${API_CONFIG.basePath}${API_CONFIG.endpoints.customActivities}`, window.location.origin);
  if (owner) url.searchParams.set('owner', owner);
  url.searchParams.set('day_utc', dayUtc);
  url.searchParams.set('line_no', String(lineNo));

  await apiRequest<unknown>(url.pathname + url.search, {
    method: 'DELETE',
    token,
  });
}
