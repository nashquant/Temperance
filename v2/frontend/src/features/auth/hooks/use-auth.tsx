import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { getMe, getOwners, login as loginRequest } from '@/features/auth/services/auth-api';
import { clearAuthSession, readAuthSession, writeAuthSession } from '@/features/auth/services/auth-storage';
import type { AuthSession, LoginPayload, MeResponse } from '@/features/auth/types';

interface AuthContextValue {
  session: AuthSession | null;
  profile: MeResponse | null;
  owners: string[];
  setOwner: (owner: string) => void;
  status: 'loading' | 'authenticated' | 'unauthenticated';
  login: (payload: LoginPayload) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const OWNER_STORAGE_KEY = 'temperance:selected-owner';

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [profile, setProfile] = useState<MeResponse | null>(null);
  const [owners, setOwners] = useState<string[]>([]);
  const [selectedOwner, setSelectedOwner] = useState<string>('');
  const [status, setStatus] = useState<'loading' | 'authenticated' | 'unauthenticated'>('loading');

  const applyOwnerScope = useCallback((me: MeResponse, ownerOptions: string[]): MeResponse => {
    const validOwners = ownerOptions.length > 0 ? ownerOptions : [me.owner];
    const storedOwner =
      typeof window !== 'undefined' ? String(window.localStorage.getItem(OWNER_STORAGE_KEY) || '').trim() : '';
    const nextOwner = validOwners.includes(storedOwner) ? storedOwner : me.owner;
    setSelectedOwner(nextOwner);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(OWNER_STORAGE_KEY, nextOwner);
    }
    return { ...me, owner: nextOwner };
  }, []);

  const bootstrap = useCallback(async () => {
    const stored = readAuthSession();
    if (!stored) {
      setOwners([]);
      setSelectedOwner('');
      setStatus('unauthenticated');
      return;
    }

    try {
      const me = await getMe(stored.token);
      const ownerOptions = stored.role === 'admin' ? (await getOwners(stored.token)).owners : [me.owner];
      setSession(stored);
      setOwners(ownerOptions);
      setProfile(applyOwnerScope(me, ownerOptions));
      setStatus('authenticated');
    } catch {
      clearAuthSession();
      setSession(null);
      setProfile(null);
      setOwners([]);
      setSelectedOwner('');
      setStatus('unauthenticated');
    }
  }, [applyOwnerScope]);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const login = useCallback(async (payload: LoginPayload) => {
    const response = await loginRequest(payload);
    const nextSession: AuthSession = {
      token: response.token,
      user: response.user,
      role: response.role,
    };

    writeAuthSession(nextSession);
    const me = await getMe(nextSession.token);
    const ownerOptions = nextSession.role === 'admin' ? (await getOwners(nextSession.token)).owners : [me.owner];

    setSession(nextSession);
    setOwners(ownerOptions);
    setProfile(applyOwnerScope(me, ownerOptions));
    setStatus('authenticated');
  }, [applyOwnerScope]);

  const logout = useCallback(() => {
    clearAuthSession();
    setSession(null);
    setProfile(null);
    setOwners([]);
    setSelectedOwner('');
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(OWNER_STORAGE_KEY);
    }
    setStatus('unauthenticated');
  }, []);

  const setOwner = useCallback((owner: string) => {
    const trimmed = String(owner || '').trim();
    if (!trimmed || !owners.includes(trimmed)) return;
    setSelectedOwner(trimmed);
    setProfile((current) => (current ? { ...current, owner: trimmed } : current));
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(OWNER_STORAGE_KEY, trimmed);
    }
  }, [owners]);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      profile,
      owners,
      setOwner,
      status,
      login,
      logout,
    }),
    [login, logout, owners, profile, session, setOwner, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
