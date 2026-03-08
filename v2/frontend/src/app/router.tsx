import { Navigate, Route, Routes } from 'react-router-dom';

import { AppLayout } from '@/components/layout/app-layout';
import { ProtectedRoute } from '@/features/auth/components/protected-route';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { LoginPage } from '@/features/auth/pages/login-page';
import { DashboardPage } from '@/features/dashboard/pages/dashboard-page';
import { WeekPlannerPage } from '@/features/week-planner/pages/week-planner-page';

function RootRedirect(): JSX.Element {
  const { status } = useAuth();

  if (status === 'loading') {
    return <div className="p-8 text-sm text-muted-foreground">Loading session...</div>;
  }

  return <Navigate to={status === 'authenticated' ? '/app/week-planner' : '/login'} replace />;
}

function PlaceholderPage({ title }: { title: string }): JSX.Element {
  return (
    <div className="rounded-lg border bg-card p-8">
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-muted-foreground">This page will be implemented next.</p>
    </div>
  );
}

export function AppRouter(): JSX.Element {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/app" element={<AppLayout />}>
          <Route path="week-planner" element={<WeekPlannerPage />} />
          <Route path="weekly-outlook" element={<Navigate to="/app/week-planner" replace />} />
          <Route path="plan-activities" element={<Navigate to="/app/week-planner" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="activities" element={<PlaceholderPage title="Activities" />} />
          <Route path="settings" element={<PlaceholderPage title="Settings" />} />
          <Route index element={<Navigate to="week-planner" replace />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
