import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { AppLayout } from '@/components/layout/app-layout';
import { ProtectedRoute } from '@/features/auth/components/protected-route';
import { useAuth } from '@/features/auth/hooks/use-auth';

const LoginPage = lazy(async () => ({
  default: (await import('@/features/auth/pages/login-page')).LoginPage,
}));
const DataExtractPage = lazy(async () => ({
  default: (await import('@/features/data-extract/pages/data-extract-page')).DataExtractPage,
}));
const DashboardPage = lazy(async () => ({
  default: (await import('@/features/dashboard/pages/dashboard-page')).DashboardPage,
}));
const AthleteProgressionPage = lazy(async () => ({
  default: (await import('@/features/athlete-progression/pages/athlete-progression-page')).AthleteProgressionPage,
}));
const AboutTemperancePage = lazy(async () => ({
  default: (await import('@/features/about/pages/about-temperance-page')).AboutTemperancePage,
}));
const SettingsPage = lazy(async () => ({
  default: (await import('@/features/settings/pages/settings-page')).SettingsPage,
}));
const WeekPlannerPage = lazy(async () => ({
  default: (await import('@/features/week-planner/pages/week-planner-page')).WeekPlannerPage,
}));
const WellnessPage = lazy(async () => ({
  default: (await import('@/features/wellness/pages/wellness-page')).WellnessPage,
}));

function RootRedirect(): JSX.Element {
  const { status } = useAuth();

  if (status === 'loading') {
    return (
      <div role="status" aria-live="polite" className="p-8 text-sm text-muted-foreground">
        Loading session…
      </div>
    );
  }

  return <Navigate to={status === 'authenticated' ? '/app/dashboard' : '/login'} replace />;
}

function RouteFallback(): JSX.Element {
  return (
    <div role="status" aria-live="polite" className="p-8 text-sm text-muted-foreground">
      Loading view…
    </div>
  );
}

function LazyRoute({ children }: { children: JSX.Element }): JSX.Element {
  return <Suspense fallback={<RouteFallback />}>{children}</Suspense>;
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
      <Route path="/login" element={<LazyRoute><LoginPage /></LazyRoute>} />

      <Route element={<ProtectedRoute />}>
        <Route path="/app" element={<AppLayout />}>
          <Route path="week-planner" element={<LazyRoute><WeekPlannerPage /></LazyRoute>} />
          <Route path="athlete-progression" element={<LazyRoute><AthleteProgressionPage /></LazyRoute>} />
          <Route path="weekly-outlook" element={<Navigate to="/app/week-planner" replace />} />
          <Route path="plan-activities" element={<Navigate to="/app/week-planner" replace />} />
          <Route path="dashboard" element={<LazyRoute><DashboardPage /></LazyRoute>} />
          <Route path="wellness" element={<LazyRoute><WellnessPage /></LazyRoute>} />
          <Route path="data-extract" element={<LazyRoute><DataExtractPage /></LazyRoute>} />
          <Route path="activities" element={<Navigate to="/app/data-extract" replace />} />
          <Route path="settings" element={<LazyRoute><SettingsPage /></LazyRoute>} />
          <Route path="about" element={<LazyRoute><AboutTemperancePage /></LazyRoute>} />
          <Route index element={<Navigate to="dashboard" replace />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
