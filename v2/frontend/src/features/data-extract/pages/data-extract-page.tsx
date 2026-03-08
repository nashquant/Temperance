import { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { useCustomActivitiesQuery } from '@/features/custom-activities/hooks/use-custom-activities-query';
import { deleteCustomActivity, ingestCustomActivities } from '@/features/custom-activities/services/custom-activities-api';
import { useDataExtractStatusQuery } from '@/features/data-extract/hooks/use-data-extract-status';
import { runComprehensiveExtract } from '@/features/data-extract/services/data-extract-api';
import { queryClient } from '@/lib/query-client';

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function DataExtractPage(): JSX.Element {
  const { session, profile } = useAuth();
  const statusQuery = useDataExtractStatusQuery();
  const customActivitiesQuery = useCustomActivitiesQuery();

  const [startDay, setStartDay] = useState('2025-01-01');
  const [incrementalOnly, setIncrementalOnly] = useState(true);
  const [includeDetails, setIncludeDetails] = useState(true);
  const [includeWellness, setIncludeWellness] = useState(false);
  const [customEntryText, setCustomEntryText] = useState('');

  const [result, setResult] = useState<string | null>(null);
  const [customResult, setCustomResult] = useState<string | null>(null);
  const [extractLogs, setExtractLogs] = useState<string[]>([]);

  const comprehensiveMutation = useMutation({
    mutationFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      setExtractLogs((previous) => [
        ...previous,
        `[${new Date().toLocaleTimeString()}] Started comprehensive extract`,
      ]);
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
      setExtractLogs((previous) => [
        ...previous,
        `[${new Date().toLocaleTimeString()}] Completed: ${response.summary}`,
        ...response.errors.map((error) => `[${new Date().toLocaleTimeString()}] Warning: ${error}`),
      ]);
    },
    onError: (error) => {
      setResult(error instanceof Error ? error.message : 'Comprehensive extract failed');
      setExtractLogs((previous) => [
        ...previous,
        `[${new Date().toLocaleTimeString()}] Failed: ${error instanceof Error ? error.message : 'Comprehensive extract failed'}`,
      ]);
    },
  });

  useEffect(() => {
    if (!comprehensiveMutation.isPending) return undefined;
    const interval = window.setInterval(() => {
      setExtractLogs((previous) => [
        ...previous,
        `[${new Date().toLocaleTimeString()}] Extract still running...`,
      ]);
    }, 3000);
    return () => window.clearInterval(interval);
  }, [comprehensiveMutation.isPending]);

  const customIngestMutation = useMutation({
    mutationFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      return ingestCustomActivities({
        token: session.token,
        owner: profile?.owner,
        entryText: customEntryText,
      });
    },
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ['custom-activities'] });
      await queryClient.invalidateQueries({ queryKey: ['data-extract-status'] });
      if (response.errors.length > 0) {
        setCustomResult(`Saved ${response.saved_count}. Some entries were skipped.`);
      } else {
        setCustomResult(`Saved ${response.saved_count} custom activit${response.saved_count === 1 ? 'y' : 'ies'}.`);
      }
      if (response.saved_count > 0) setCustomEntryText('');
    },
    onError: (error) => {
      setCustomResult(error instanceof Error ? error.message : 'Unable to save custom activities.');
    },
  });

  const customDeleteMutation = useMutation({
    mutationFn: async ({ dayUtc, lineNo }: { dayUtc: string; lineNo: number }) => {
      if (!session?.token) throw new Error('Missing auth token');
      await deleteCustomActivity({
        token: session.token,
        owner: profile?.owner,
        dayUtc,
        lineNo,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['custom-activities'] });
      await queryClient.invalidateQueries({ queryKey: ['data-extract-status'] });
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
          <div className="rounded-md border border-border/70 bg-muted/20 p-2">
            <div className="mb-1 flex items-center justify-between">
              <p className="text-xs font-medium text-muted-foreground">Extraction logs</p>
              <Button
                variant="outline"
                onClick={() => setExtractLogs([])}
                disabled={comprehensiveMutation.isPending || extractLogs.length === 0}
              >
                Clear
              </Button>
            </div>
            <div className="max-h-44 overflow-auto rounded border border-border/70 bg-background/30 p-2 font-mono text-xs">
              {extractLogs.length === 0 ? (
                <p className="text-muted-foreground">No logs yet. Run an extract to see progression.</p>
              ) : (
                extractLogs.map((line, index) => (
                  <p key={`${line}-${index}`} className="whitespace-pre-wrap text-foreground/90">
                    {line}
                  </p>
                ))
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {result ? <p className="text-sm text-muted-foreground">{result}</p> : null}

      <Card>
        <CardContent className="space-y-3 p-4">
          <p className="text-sm font-medium">Custom Activities</p>
          <p className="text-xs text-muted-foreground">
            Use <code>[date]:[activity]</code>. Date formats like <code>3Mar26</code>, <code>2026-03-26</code>, or <code>26/03/2026</code>.
            You can add multiple entries separated by new line, <code>;</code>, or <code>,</code>.
          </p>
          <textarea
            className="min-h-[84px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
            value={customEntryText}
            onChange={(event) => setCustomEntryText(event.target.value)}
            placeholder="e.g. 3Mar26: 80min elliptical @140bpm; 2026-03-26: 10min run @4:50 + 5x6min @3:40/km"
          />
          <div className="flex items-center gap-2">
            <Button onClick={() => customIngestMutation.mutate()} disabled={customIngestMutation.isPending || !customEntryText.trim()}>
              {customIngestMutation.isPending ? 'Saving...' : 'Save custom entry'}
            </Button>
            {customResult ? <p className="text-xs text-muted-foreground">{customResult}</p> : null}
          </div>

          {customActivitiesQuery.data?.weeks?.length ? (
            <div className="grid gap-2 md:grid-cols-4">
              {customActivitiesQuery.data.weeks.slice(0, 4).map((week) => (
                <div key={week.week_start} className="rounded border p-2 text-xs">
                  <p className="text-muted-foreground">{week.week_start} - {week.week_end}</p>
                  <p className="font-semibold">{week.custom_activities} activities</p>
                  <p className="text-muted-foreground">
                    TSS {Math.round(week.tss)} · rTSS {Math.round(week.rtss)} · Dist {Math.round(week.distance_eqv_km)} kmeq
                  </p>
                </div>
              ))}
            </div>
          ) : null}

          <div className="overflow-x-auto rounded border">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-2 py-2">Day</th>
                  <th className="px-2 py-2">Activity</th>
                  <th className="px-2 py-2">Text</th>
                  <th className="px-2 py-2">Pace · IF</th>
                  <th className="px-2 py-2">TSS · rTSS</th>
                  <th className="px-2 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(customActivitiesQuery.data?.rows ?? []).slice(0, 30).map((row) => (
                  <tr key={`${row.day_utc}-${row.line_no}`} className="border-t">
                    <td className="px-2 py-2">{row.day_utc}</td>
                    <td className="px-2 py-2">{row.activity}</td>
                    <td className="px-2 py-2">{row.activity_text}</td>
                    <td className="px-2 py-2">{row.pace_label} · IF {Math.round(row.if_proxy_pct)}%</td>
                    <td className="px-2 py-2">TSS {Math.round(row.tss)} · rTSS {Math.round(row.rtss)}</td>
                    <td className="px-2 py-2">
                      <Button
                        variant="outline"
                        onClick={() => customDeleteMutation.mutate({ dayUtc: row.day_utc, lineNo: row.line_no })}
                        disabled={customDeleteMutation.isPending}
                      >
                        Delete
                      </Button>
                    </td>
                  </tr>
                ))}
                {!customActivitiesQuery.isLoading && (customActivitiesQuery.data?.rows.length ?? 0) === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-2 py-3 text-center text-xs text-muted-foreground">
                      No custom activities yet.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

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
