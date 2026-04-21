import { useQuery } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/hooks/use-auth';
import { getCoachSnapshot } from '@/features/coach-snapshot/services/coach-snapshot-api';

export function useCoachSnapshotQuery(enabled = true) {
  const { session, profile } = useAuth();

  return useQuery({
    queryKey: ['coach-snapshot', profile?.owner],
    queryFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      return getCoachSnapshot({ token: session.token, owner: profile?.owner });
    },
    enabled: Boolean(session?.token) && enabled,
    staleTime: 60_000,
  });
}
