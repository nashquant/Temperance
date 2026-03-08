import { API_CONFIG } from '@/api/config';
import { apiRequest } from '@/api/http-client';
import type {
  ComprehensiveExtractRequest,
  ComprehensiveExtractResponse,
  DataExtractStatusResponse,
  SyncRequest,
  SyncResponse,
} from '@/features/data-extract/types/data-extract';

interface BaseParams {
  token: string;
  owner?: string;
}

function withOwner(path: string, owner?: string): string {
  if (!owner) return path;
  const qs = new URLSearchParams({ owner });
  return `${path}?${qs.toString()}`;
}

export async function getDataExtractStatus({ token, owner }: BaseParams): Promise<DataExtractStatusResponse> {
  return apiRequest<DataExtractStatusResponse>(withOwner(API_CONFIG.endpoints.dataExtractStatus, owner), {
    method: 'GET',
    token,
  });
}

export async function runSync({ token, owner, payload }: BaseParams & { payload: SyncRequest }): Promise<SyncResponse> {
  return apiRequest<SyncResponse>(withOwner(API_CONFIG.endpoints.dataExtractSync, owner), {
    method: 'POST',
    token,
    body: payload,
  });
}

export async function runComprehensiveExtract({ token, owner, payload }: BaseParams & { payload: ComprehensiveExtractRequest }): Promise<ComprehensiveExtractResponse> {
  return apiRequest<ComprehensiveExtractResponse>(withOwner(API_CONFIG.endpoints.dataExtractComprehensive, owner), {
    method: 'POST',
    token,
    body: payload,
  });
}
