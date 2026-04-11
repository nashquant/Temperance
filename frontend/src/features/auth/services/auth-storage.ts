import { COOKIE_AUTH_TOKEN } from '@/api/auth-token';
import type { AuthSession } from '@/features/auth/types';

const AUTH_STORAGE_KEY = 'temperance.session';
const LEGACY_AUTH_STORAGE_KEY = 'temperance.session.v1';

export function readAuthSession(): AuthSession | null {
  const raw = localStorage.getItem(AUTH_STORAGE_KEY) ?? localStorage.getItem(LEGACY_AUTH_STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as AuthSession;
    if (!parsed?.user || !parsed?.role) return null;
    return { ...parsed, token: COOKIE_AUTH_TOKEN };
  } catch {
    return null;
  }
}

export function writeAuthSession(session: AuthSession): void {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ user: session.user, role: session.role }));
  localStorage.removeItem(LEGACY_AUTH_STORAGE_KEY);
}

export function clearAuthSession(): void {
  localStorage.removeItem(AUTH_STORAGE_KEY);
  localStorage.removeItem(LEGACY_AUTH_STORAGE_KEY);
}
