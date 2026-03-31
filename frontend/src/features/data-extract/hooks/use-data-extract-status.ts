import { useQuery } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/hooks/use-auth';
import { getDataExtractStatus } from '@/features/data-extract/services/data-extract-api';

export function useDataExtractStatusQuery() {
  const { session, profile } = useAuth();

  return useQuery({
    queryKey: ['data-extract-status', profile?.owner],
    queryFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      return getDataExtractStatus({ token: session.token, owner: profile?.owner });
    },
    enabled: Boolean(session?.token),
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.extract_progress?.running ? 2500 : false;
    },
  });
}
