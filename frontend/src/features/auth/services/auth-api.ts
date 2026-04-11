import { API_CONFIG } from '@/api/config';
import { apiRequest } from '@/api/http-client';
import type { LoginPayload, MeResponse, OwnersResponse } from '@/features/auth/types';

interface LoginResponse {
  token: string;
  user: string;
  role: 'admin' | 'viewer';
}

export async function login(payload: LoginPayload): Promise<LoginResponse> {
  return apiRequest<LoginResponse>(API_CONFIG.endpoints.login, {
    method: 'POST',
    body: payload,
  });
}

export async function logout(): Promise<void> {
  await apiRequest<{ ok: boolean }>(API_CONFIG.endpoints.logout, {
    method: 'POST',
  });
}

export async function getMe(token?: string | null): Promise<MeResponse> {
  return apiRequest<MeResponse>(API_CONFIG.endpoints.me, {
    method: 'GET',
    token,
  });
}

export async function getOwners(token?: string | null): Promise<OwnersResponse> {
  return apiRequest<OwnersResponse>(API_CONFIG.endpoints.owners, {
    method: 'GET',
    token,
  });
}
