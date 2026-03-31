import { useQuery } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/hooks/use-auth';
import { getPlannedActivities } from '@/features/plan-activities/services/plan-activities-api';

export function usePlanActivitiesQuery(weeks = 4) {
  const { session, profile } = useAuth();

  return useQuery({
    queryKey: ['plan-activities', profile?.owner, weeks],
    queryFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      return getPlannedActivities({
        token: session.token,
        owner: profile?.owner,
        weeks,
      });
    },
    enabled: Boolean(session?.token),
  });
}
