import type * as React from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';

/* ------------------------------------------------------------------ */
/*  Skeleton presets                                                   */
/* ------------------------------------------------------------------ */

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

/* ------------------------------------------------------------------ */
/*  Error alert                                                        */
/* ------------------------------------------------------------------ */

function QueryError({ title, error }: { title: string; error: unknown }): JSX.Element {
  const message = error instanceof Error ? error.message : 'Unexpected error.';
  return (
    <Alert className="border-destructive/50 text-destructive">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription className="text-destructive/90">{message}</AlertDescription>
    </Alert>
  );
}

/* ------------------------------------------------------------------ */
/*  QueryShell                                                         */
/* ------------------------------------------------------------------ */

interface QueryShellProps {
  /** React Query result fields. */
  isLoading: boolean;
  isError: boolean;
  error?: unknown;
  /** Human-readable label for the error alert, e.g. "Unable to load dashboard". */
  errorTitle: string;
  /** Skeleton preset name or a custom ReactNode. Default: "page". */
  skeleton?: SkeletonPreset | React.ReactNode;
  children: React.ReactNode;
}

/**
 * Standardised loading / error / content shell for pages backed by a
 * React Query hook.  Replaces the per-page copy-pasted skeleton + alert
 * blocks with one declarative wrapper.
 *
 * Usage:
 * ```tsx
 * <QueryShell isLoading={query.isLoading} isError={query.isError}
 *   error={query.error} errorTitle="Unable to load wellness">
 *   {query.data ? <Content data={query.data} /> : null}
 * </QueryShell>
 * ```
 */
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
