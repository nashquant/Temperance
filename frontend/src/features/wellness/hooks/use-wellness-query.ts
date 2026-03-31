import { useQuery } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/hooks/use-auth';
import { getWellness } from '@/features/wellness/services/wellness-api';
import type { WellnessAggregation } from '@/features/wellness/types';

export function useWellnessQuery(days: number, aggregation: WellnessAggregation) {
  const { session, profile } = useAuth();

  return useQuery({
    queryKey: ['wellness', profile?.owner, days, aggregation],
    queryFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      return getWellness({
        token: session.token,
        owner: profile?.owner,
        days,
        aggregation,
      });
    },
    enabled: Boolean(session?.token),
  });
}
