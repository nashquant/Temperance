import { API_CONFIG } from '@/api/config';
import { apiRequest } from '@/api/http-client';
import type { SettingsResponse, UpdateSettingsRequest } from '@/features/settings/types/settings';

interface SettingsParams {
  token: string;
  owner?: string;
}

export async function getSettings({ token, owner }: SettingsParams): Promise<SettingsResponse> {
  const search = new URLSearchParams();
  if (owner) search.set('owner', owner);
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return apiRequest<SettingsResponse>(`${API_CONFIG.endpoints.settings}${suffix}`, {
    method: 'GET',
    token,
  });
}

export async function updateSettings({ token, owner, payload }: SettingsParams & { payload: UpdateSettingsRequest }): Promise<{ updated: string[] }> {
  const search = new URLSearchParams();
  if (owner) search.set('owner', owner);
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return apiRequest<{ updated: string[] }>(`${API_CONFIG.endpoints.settings}${suffix}`, {
    method: 'PUT',
    token,
    body: payload,
  });
}
