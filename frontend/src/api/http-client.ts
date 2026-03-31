import { API_CONFIG } from '@/api/config';

export class ApiError extends Error {
  readonly status: number;
  readonly detail?: string;

  constructor(message: string, status: number, detail?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  token?: string | null;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, token, ...rest } = options;

  const response = await fetch(`${API_CONFIG.basePath}${path}`, {
    ...rest,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(headers ?? {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    const detail = typeof errorPayload?.detail === 'string' ? errorPayload.detail : undefined;
    throw new ApiError(detail ?? `Request failed (${response.status})`, response.status, detail);
  }

  return (await response.json()) as T;
}
