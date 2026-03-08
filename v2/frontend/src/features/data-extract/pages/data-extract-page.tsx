import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { useDataExtractStatusQuery } from '@/features/data-extract/hooks/use-data-extract-status';
import { runComprehensiveExtract } from '@/features/data-extract/services/data-extract-api';
import { queryClient } from '@/lib/query-client';

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function DataExtractPage(): JSX.Element {
  const { session, profile } = useAuth();
  const statusQuery = useDataExtractStatusQuery();

  const [startDay, setStartDay] = useState('2025-01-01');
  const [incrementalOnly, setIncrementalOnly] = useState(true);
  const [includeDetails, setIncludeDetails] = useState(true);
  const [includeWellness, setIncludeWellness] = useState(false);

  const [result, setResult] = useState<string | null>(null);

  const comprehensiveMutation = useMutation({
    mutationFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      return runComprehensiveExtract({
        token: session.token,
        owner: profile?.owner,
        payload: {
          start_day: startDay,
          incremental_only: incrementalOnly,
          include_details: includeDetails,
          include_wellness: includeWellness,
          verify_raw_integrity: false,
        },
      });
    },
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ['data-extract-status'] });
      setResult(`Comprehensive extract complete: ${response.summary}`);
    },
    onError: (error) => {
      setResult(error instanceof Error ? error.message : 'Comprehensive extract failed');
    },
  });

  if (statusQuery.isLoading) {
    return (
      <section className="space-y-3">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-40 w-full" />
      </section>
    );
  }

  if (statusQuery.isError) {
    return (
      <Alert className="border-red-300 text-red-700 dark:border-red-900 dark:text-red-300">
        <AlertTitle>Unable to load data extract status</AlertTitle>
        <AlertDescription>{statusQuery.error instanceof Error ? statusQuery.error.message : 'Unexpected error.'}</AlertDescription>
      </Alert>
    );
  }

  const status = statusQuery.data;

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Data Extract</h1>
      </div>

      <Card>
        <CardContent className="space-y-3 p-4">
          <p className="text-sm font-medium">Comprehensive Garmin Extract</p>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <p className="mb-1 text-xs text-muted-foreground">Start day</p>
              <input className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm" type="date" max={todayIso()} value={startDay} onChange={(event) => setStartDay(event.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={incrementalOnly} onChange={(event) => setIncrementalOnly(event.target.checked)} /> Incremental only</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={includeDetails} onChange={(event) => setIncludeDetails(event.target.checked)} /> Include details</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={includeWellness} onChange={(event) => setIncludeWellness(event.target.checked)} /> Include sleep + wellness</label>
          </div>
          <Button onClick={() => comprehensiveMutation.mutate()} disabled={comprehensiveMutation.isPending}>{comprehensiveMutation.isPending ? 'Running extract...' : 'Run comprehensive extract'}</Button>
        </CardContent>
      </Card>

      {result ? <p className="text-sm text-muted-foreground">{result}</p> : null}

      <Card>
        <CardContent className="space-y-2 p-4 text-sm">
          <p><span className="text-muted-foreground">DB:</span> {status?.db_path}</p>
          <p><span className="text-muted-foreground">Import dir:</span> {status?.import_dir}</p>
          <p><span className="text-muted-foreground">Garmin creds:</span> {status?.garmin_credentials_available ? 'available' : 'missing'}</p>
          {status?.last_sync ? (
            <p><span className="text-muted-foreground">Last sync:</span> {status.last_sync.sync_time_utc} | {status.last_sync.source} | {status.last_sync.success ? 'success' : 'failed'}</p>
          ) : (
            <p className="text-muted-foreground">No sync has been run yet.</p>
          )}
          <p className="text-muted-foreground">Local records:</p>
          <div className="grid gap-2 md:grid-cols-3">
            {Object.entries(status?.counts ?? {}).map(([key, value]) => (
              <div key={key} className="rounded border p-2 text-xs">
                <p className="text-muted-foreground">{key}</p>
                <p className="font-semibold text-foreground">{value}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
