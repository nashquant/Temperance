import { useQuery } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/hooks/use-auth';
import { getWeeklyOutlook } from '@/features/weekly-outlook/services/weekly-outlook-api';
import type { WeeklyCompare, WeeklyMetric } from '@/features/weekly-outlook/types/weekly-outlook';
import { mapWeeklyOutlookResponse } from '@/features/weekly-outlook/utils/weekly-outlook-mapper';

interface UseWeeklyOutlookQueryOptions {
  enabled?: boolean;
}

export function useWeeklyOutlookQuery(
  metric: WeeklyMetric,
  compare: WeeklyCompare,
  weekStart?: string,
  options?: UseWeeklyOutlookQueryOptions,
) {
  const { session, profile } = useAuth();
  const enabled = options?.enabled ?? true;

  return useQuery({
    queryKey: ['weekly-outlook', profile?.owner, metric, compare, weekStart ?? 'current'],
    queryFn: async () => {
      if (!session?.token) {
        throw new Error('Missing auth token');
      }

      const raw = await getWeeklyOutlook({
        token: session.token,
        owner: profile?.owner,
        metric,
        compare,
        weekStart,
      });

      // Distance chart colors are based on day TSS thresholds.
      // Fetch TSS in parallel path and merge day-level TSS basis when needed.
      if (metric === 'distance') {
        const tssRaw = await getWeeklyOutlook({
          token: session.token,
          owner: profile?.owner,
          metric: 'tss',
          compare,
          weekStart,
        });
        const dayTss = new Map(tssRaw.rows.map((row) => [row.day, Number(row.current || 0)]));
        raw.rows = raw.rows.map((row) => ({
          ...row,
          current_tss: dayTss.get(row.day) ?? row.current_tss ?? 0,
        }));
      }
      return mapWeeklyOutlookResponse(raw);
    },
    enabled: Boolean(session?.token) && enabled,
  });
}
