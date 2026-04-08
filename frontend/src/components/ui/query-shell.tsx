import type * as React from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';

/** Page with a header bar and one or two content blocks. */
function PageSkeleton(): JSX.Element {
  return (
    <div className="space-y-3">
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-64 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

/** Compact variant: header + single content area. */
function CompactSkeleton(): JSX.Element {
  return (
    <div className="space-y-3">
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

const skeletonPresets = {
  page: <PageSkeleton />,
  compact: <CompactSkeleton />,
} as const;

export type SkeletonPreset = keyof typeof skeletonPresets;

function QueryError({ title, error }: { title: string; error: unknown }): JSX.Element {
  const message = error instanceof Error ? error.message : 'Unexpected error.';
  return (
    <Alert className="border-destructive/50 text-destructive">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription className="text-destructive/90">{message}</AlertDescription>
    </Alert>
  );
}

interface QueryShellProps {
  isLoading: boolean;
  isError: boolean;
  error?: unknown;
  errorTitle: string;
  skeleton?: SkeletonPreset | React.ReactNode;
  children: React.ReactNode;
}

/** Shared loading / error / content shell for React Query-backed pages. */
export function QueryShell({
  isLoading,
  isError,
  error,
  errorTitle,
  skeleton = 'page',
  children,
}: QueryShellProps): JSX.Element {
  if (isLoading) {
    const resolved =
      typeof skeleton === 'string' ? (skeletonPresets[skeleton as SkeletonPreset] ?? skeletonPresets.page) : skeleton;
    return <>{resolved}</>;
  }

  if (isError) {
    return <QueryError title={errorTitle} error={error} />;
  }

  return <>{children}</>;
}
