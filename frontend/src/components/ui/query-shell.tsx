import type * as React from 'react';
import { useEffect, useState } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

function SkeletonBlock({ label, className }: { label: string; className: string }): JSX.Element {
  return (
    <div className={cn('relative overflow-hidden rounded-xl border border-border/70 bg-card/55 p-4', className)}>
      <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-foreground/80">
        {label}
      </span>
      <div className="mt-4 space-y-3">
        <Skeleton className="h-3 w-2/3 bg-muted/80" />
        <Skeleton className="h-3 w-1/2 bg-muted/70" />
        <Skeleton className="h-3 w-5/6 bg-muted/60" />
      </div>
    </div>
  );
}

function LoadingTimeoutNotice({ title }: { title: string }): JSX.Element {
  return (
    <div className="rounded-xl border border-border/70 bg-card/60 p-4 text-sm text-muted-foreground">
      <p className="font-medium text-foreground">Still loading.</p>
      <p className="mt-1">
        {title.replace(/^Unable to load /i, '')} is taking longer than expected. Keep waiting, or refresh if the data
        does not appear.
      </p>
      <button
        type="button"
        className="mt-3 min-h-11 rounded-md border border-border px-4 text-sm font-medium text-foreground transition-colors hover:bg-accent"
        onClick={() => window.location.reload()}
      >
        Refresh page
      </button>
    </div>
  );
}

/** Page with labeled blocks that match the expected information shape. */
function PageSkeleton({ showTimeout, errorTitle }: { showTimeout: boolean; errorTitle: string }): JSX.Element {
  return (
    <div className="space-y-3">
      <SkeletonBlock label="Loading summary" className="min-h-24 w-full" />
      <SkeletonBlock label="Loading chart" className="min-h-64 w-full" />
      <SkeletonBlock label="Loading details" className="min-h-64 w-full" />
      {showTimeout ? <LoadingTimeoutNotice title={errorTitle} /> : null}
    </div>
  );
}

/** Compact variant: header + single content area. */
function CompactSkeleton({ showTimeout, errorTitle }: { showTimeout: boolean; errorTitle: string }): JSX.Element {
  return (
    <div className="space-y-3">
      <SkeletonBlock label="Loading status" className="min-h-24 w-full" />
      <SkeletonBlock label="Loading form" className="min-h-40 w-full" />
      {showTimeout ? <LoadingTimeoutNotice title={errorTitle} /> : null}
    </div>
  );
}

const skeletonPresets = {
  page: PageSkeleton,
  compact: CompactSkeleton,
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
  const [showLoadingTimeout, setShowLoadingTimeout] = useState(false);

  useEffect(() => {
    if (!isLoading) {
      setShowLoadingTimeout(false);
      return;
    }

    const timeoutId = window.setTimeout(() => setShowLoadingTimeout(true), 8000);
    return () => window.clearTimeout(timeoutId);
  }, [isLoading]);

  if (isLoading) {
    const resolved =
      typeof skeleton === 'string'
        ? (skeletonPresets[skeleton as SkeletonPreset] ?? skeletonPresets.page)({
            showTimeout: showLoadingTimeout,
            errorTitle,
          })
        : skeleton;
    return (
      <div role="status" aria-live="polite" aria-busy="true">
        {resolved}
      </div>
    );
  }

  if (isError) {
    return <QueryError title={errorTitle} error={error} />;
  }

  return <>{children}</>;
}
