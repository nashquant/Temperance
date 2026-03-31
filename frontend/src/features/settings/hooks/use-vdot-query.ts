import { useQuery } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/hooks/use-auth';
import { getVdot } from '@/features/settings/services/settings-api';

export function useVdotQuery() {
  const { session, profile } = useAuth();

  return useQuery({
    queryKey: ['vdot', profile?.owner],
    queryFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      return getVdot({ token: session.token, owner: profile?.owner });
    },
    enabled: Boolean(session?.token),
  });
}
