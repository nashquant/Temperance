import { useQuery } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/hooks/use-auth';
import { getAthleteProgression } from '@/features/athlete-progression/services/athlete-progression-api';
import type {
  ProgressionActivityFilter,
  ProgressionAggregation,
} from '@/features/athlete-progression/types/athlete-progression';

export function useAthleteProgressionQuery(
  days: number,
  aggregation: ProgressionAggregation,
  activityFilter: ProgressionActivityFilter,
) {
  const { session, profile } = useAuth();

  return useQuery({
    queryKey: ['athlete-progression', profile?.owner, days, aggregation, activityFilter],
    queryFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      return getAthleteProgression({
        token: session.token,
        owner: profile?.owner,
        days,
        aggregation,
        activityFilter,
      });
    },
    enabled: Boolean(session?.token),
  });
}
