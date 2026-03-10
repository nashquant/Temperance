import { Navigate, Route, Routes } from 'react-router-dom';

import { AppLayout } from '@/components/layout/app-layout';
import { ProtectedRoute } from '@/features/auth/components/protected-route';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { LoginPage } from '@/features/auth/pages/login-page';
import { DataExtractPage } from '@/features/data-extract/pages/data-extract-page';
import { DashboardPage } from '@/features/dashboard/pages/dashboard-page';
import { AthleteProgressionPage } from '@/features/athlete-progression/pages/athlete-progression-page';
import { AboutTemperancePage } from '@/features/about/pages/about-temperance-page';
import { SettingsPage } from '@/features/settings/pages/settings-page';
import { WeekPlannerPage } from '@/features/week-planner/pages/week-planner-page';
import { WellnessPage } from '@/features/wellness/pages/wellness-page';

function RootRedirect(): JSX.Element {
  const { status } = useAuth();

  if (status === 'loading') {
    return <div className="p-8 text-sm text-muted-foreground">Loading session...</div>;
  }

  return <Navigate to={status === 'authenticated' ? '/app/dashboard' : '/login'} replace />;
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
          <Route path="athlete-progression" element={<AthleteProgressionPage />} />
          <Route path="wellness" element={<WellnessPage />} />
          <Route path="data-extract" element={<DataExtractPage />} />
          <Route path="activities" element={<Navigate to="/app/data-extract" replace />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="about" element={<AboutTemperancePage />} />
          <Route index element={<Navigate to="dashboard" replace />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
