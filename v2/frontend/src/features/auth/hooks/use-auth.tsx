import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { getMe, login as loginRequest } from '@/features/auth/services/auth-api';
import { clearAuthSession, readAuthSession, writeAuthSession } from '@/features/auth/services/auth-storage';
import type { AuthSession, LoginPayload, MeResponse } from '@/features/auth/types';

interface AuthContextValue {
  session: AuthSession | null;
  profile: MeResponse | null;
  status: 'loading' | 'authenticated' | 'unauthenticated';
  login: (payload: LoginPayload) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [profile, setProfile] = useState<MeResponse | null>(null);
  const [status, setStatus] = useState<'loading' | 'authenticated' | 'unauthenticated'>('loading');

  const bootstrap = useCallback(async () => {
    const stored = readAuthSession();
    if (!stored) {
      setStatus('unauthenticated');
      return;
    }

    try {
      const me = await getMe(stored.token);
      setSession(stored);
      setProfile(me);
      setStatus('authenticated');
    } catch {
      clearAuthSession();
      setSession(null);
      setProfile(null);
      setStatus('unauthenticated');
    }
  }, []);

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

    setSession(nextSession);
    setProfile(me);
    setStatus('authenticated');
  }, []);

  const logout = useCallback(() => {
    clearAuthSession();
    setSession(null);
    setProfile(null);
    setStatus('unauthenticated');
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      profile,
      status,
      login,
      logout,
    }),
    [login, logout, profile, session, status],
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
