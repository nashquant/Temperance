import { useQuery } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/hooks/use-auth';
import { getActivityDetail } from '@/features/dashboard/services/activity-detail-api';

export function useActivityDetailQuery(activityId: string | null) {
  const { session, profile } = useAuth();

  return useQuery({
    queryKey: ['activity-detail', profile?.owner, activityId],
    queryFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      if (!activityId) throw new Error('Missing activity id');
      return getActivityDetail({
        token: session.token,
        owner: profile?.owner,
        activityId,
      });
    },
    enabled: Boolean(session?.token && activityId),
  });
}

