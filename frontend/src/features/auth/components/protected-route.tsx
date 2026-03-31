import { Navigate, Outlet } from 'react-router-dom';

import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/hooks/use-auth';

export function ProtectedRoute(): JSX.Element {
  const { status } = useAuth();

  if (status === 'loading') {
    return (
      <div className="p-8">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="mt-4 h-56 w-full" />
      </div>
    );
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
