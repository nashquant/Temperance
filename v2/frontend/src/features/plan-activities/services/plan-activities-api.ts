import { API_CONFIG } from '@/api/config';
import { apiRequest } from '@/api/http-client';
import type { PlannedActivitiesResponse } from '@/features/plan-activities/types/plan-activities';

interface PlannedActivitiesParams {
  token: string;
  owner?: string;
  weeks?: number;
}

export async function getPlannedActivities({ token, owner, weeks = 4 }: PlannedActivitiesParams): Promise<PlannedActivitiesResponse> {
  const search = new URLSearchParams({ weeks: String(weeks) });
  if (owner) search.set('owner', owner);

  return apiRequest<PlannedActivitiesResponse>(`${API_CONFIG.endpoints.plannedActivities}?${search.toString()}`, {
    method: 'GET',
    token,
  });
}

interface PlannedManualDoneParams {
  token: string;
  dayUtc: string;
  lineNo: number;
  manualDone: boolean;
  owner?: string;
}

export async function setPlannedManualDone({
  token,
  dayUtc,
  lineNo,
  manualDone,
  owner,
}: PlannedManualDoneParams): Promise<void> {
  const search = new URLSearchParams();
  if (owner) search.set('owner', owner);

  await apiRequest<{ updated: boolean }>(
    `${API_CONFIG.endpoints.plannedManualDone}${search.toString() ? `?${search.toString()}` : ''}`,
    {
      method: 'PATCH',
      token,
      body: {
        day_utc: dayUtc,
        line_no: lineNo,
        manual_done: manualDone,
      },
    },
  );
}

interface PlannedDeleteParams {
  token: string;
  dayUtc: string;
  lineNo: number;
  owner?: string;
}

export async function deletePlannedActivity({ token, dayUtc, lineNo, owner }: PlannedDeleteParams): Promise<void> {
  const search = new URLSearchParams({ day_utc: dayUtc, line_no: String(lineNo) });
  if (owner) search.set('owner', owner);

  await apiRequest<{ deleted: number }>(`${API_CONFIG.endpoints.plannedActivities}?${search.toString()}`, {
    method: 'DELETE',
    token,
  });
}
