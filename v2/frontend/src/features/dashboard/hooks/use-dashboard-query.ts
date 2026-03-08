import { useQuery } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/hooks/use-auth';
import { getDashboard } from '@/features/dashboard/services/dashboard-api';
import type { DashboardSportFilter } from '@/features/dashboard/types/dashboard';

function mapSportFilterToApi(filter: DashboardSportFilter): string | undefined {
  if (filter === 'all') return undefined;
  if (filter === 'running') return 'run';
  if (filter === 'treadmill') return 'treadmill';
  if (filter === 'cycling') return 'cycl';
  return 'ellipt';
}

export function useDashboardQuery(weeks: number, sportFilter: DashboardSportFilter) {
  const { session, profile } = useAuth();

  return useQuery({
    queryKey: ['dashboard', profile?.owner, weeks, sportFilter],
    queryFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      return getDashboard({
        token: session.token,
        owner: profile?.owner,
        weeks,
        sport: mapSportFilterToApi(sportFilter),
      });
    },
    enabled: Boolean(session?.token),
  });
}
