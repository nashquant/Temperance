import { useQuery } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/hooks/use-auth';
import { getWeeklyOutlook } from '@/features/weekly-outlook/services/weekly-outlook-api';
import type { WeeklyCompare, WeeklyMetric } from '@/features/weekly-outlook/types/weekly-outlook';
import { mapWeeklyOutlookResponse } from '@/features/weekly-outlook/utils/weekly-outlook-mapper';

export function useWeeklyOutlookQuery(metric: WeeklyMetric, compare: WeeklyCompare) {
  const { session, profile } = useAuth();

  return useQuery({
    queryKey: ['weekly-outlook', profile?.owner, metric, compare],
    queryFn: async () => {
      if (!session?.token) {
        throw new Error('Missing auth token');
      }

      const raw = await getWeeklyOutlook({
        token: session.token,
        owner: profile?.owner,
        metric,
        compare,
      });
      return mapWeeklyOutlookResponse(raw);
    },
    enabled: Boolean(session?.token),
  });
}
