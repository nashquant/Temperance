import { useQuery } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/hooks/use-auth';
import { getCustomActivities } from '@/features/custom-activities/services/custom-activities-api';

export function useCustomActivitiesQuery() {
  const { session, profile } = useAuth();

  return useQuery({
    queryKey: ['custom-activities', profile?.owner],
    queryFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      return getCustomActivities({ token: session.token, owner: profile?.owner });
    },
    enabled: Boolean(session?.token),
  });
}
