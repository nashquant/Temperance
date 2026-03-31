import { useQuery } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/hooks/use-auth';
import { getSettings } from '@/features/settings/services/settings-api';

export function useSettingsQuery() {
  const { session, profile } = useAuth();

  return useQuery({
    queryKey: ['settings', profile?.owner],
    queryFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      return getSettings({ token: session.token, owner: profile?.owner });
    },
    enabled: Boolean(session?.token),
  });
}
