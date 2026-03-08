import { Navigate } from 'react-router-dom';

import { LoginForm } from '@/features/auth/components/login-form';
import { useAuth } from '@/features/auth/hooks/use-auth';

export function LoginPage(): JSX.Element {
  const { status } = useAuth();

  if (status === 'authenticated') {
    return <Navigate to="/app/weekly-outlook" replace />;
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-background via-background to-muted/40 p-6">
      <div className="mx-auto flex min-h-[80vh] max-w-6xl items-center justify-center">
        <LoginForm />
      </div>
    </main>
  );
}
