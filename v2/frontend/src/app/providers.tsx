import * as React from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';

import { AuthProvider } from '@/features/auth/hooks/use-auth';
import { queryClient } from '@/lib/query-client';

export function AppProviders({ children }: { children: React.ReactNode }): JSX.Element {
  const rawBase = (import.meta.env.BASE_URL || '/').replace(/\/+$/, '');
  const routerBase = rawBase === '' ? '/' : rawBase;

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter basename={routerBase}>{children}</BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
