import * as React from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { COOKIE_AUTH_TOKEN } from "@/api/auth-token";
import { AuthProvider } from "@/features/auth/hooks/use-auth";
import { queryClient } from "@/lib/query-client";
import { getDashboard } from "@/features/dashboard/services/dashboard-api";

const DASHBOARD_PREFETCH_WEEKS = 26;

function DashboardPrefetch(): null {
  React.useEffect(() => {
    void queryClient.prefetchQuery({
      queryKey: ["dashboard", undefined, DASHBOARD_PREFETCH_WEEKS, 0, "all"],
      queryFn: () =>
        getDashboard({
          token: COOKIE_AUTH_TOKEN,
          owner: undefined,
          weeks: DASHBOARD_PREFETCH_WEEKS,
          weekOffset: 0,
          sport: undefined,
        }),
      staleTime: 60_000,
    });
  }, []);
  return null;
}

export function AppProviders({
  children,
}: {
  children: React.ReactNode;
}): JSX.Element {
  const rawBase = (import.meta.env.BASE_URL || "/").replace(/\/+$/, "");
  const routerBase = rawBase === "" ? "/" : rawBase;

  return (
    <QueryClientProvider client={queryClient}>
      <DashboardPrefetch />
      <AuthProvider>
        <BrowserRouter basename={routerBase}>{children}</BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
