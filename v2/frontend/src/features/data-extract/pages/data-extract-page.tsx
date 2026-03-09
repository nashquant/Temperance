import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { useCustomActivitiesQuery } from '@/features/custom-activities/hooks/use-custom-activities-query';
import {
  deleteCustomActivity,
  ingestCustomActivities,
  updateCustomActivityWorkout,
} from '@/features/custom-activities/services/custom-activities-api';
import { useDataExtractStatusQuery } from '@/features/data-extract/hooks/use-data-extract-status';
import { runComprehensiveExtract, setGarminCredentials } from '@/features/data-extract/services/data-extract-api';
import { PlannedMetricSelector } from '@/features/plan-activities/components/planned-metric-selector';
import { PlannedWeekChart } from '@/features/plan-activities/components/planned-week-chart';
import type { PlannedMetricView } from '@/features/plan-activities/types/plan-activities';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { queryClient } from '@/lib/query-client';

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function DataExtractPage(): JSX.Element {
  const surfaceClassName =
    'overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]';
  const { session, profile } = useAuth();
  const statusQuery = useDataExtractStatusQuery();
  const customActivitiesQuery = useCustomActivitiesQuery();

  const [startDay, setStartDay] = useState('2025-01-01');
  const [incrementalOnly, setIncrementalOnly] = useState(true);
  const [includeDetails, setIncludeDetails] = useState(true);
  const [includeWellness, setIncludeWellness] = useState(false);
  const [customEntryText, setCustomEntryText] = useState('');
  const [customSelectedWeek, setCustomSelectedWeek] = useState('');
  const [customMetric, setCustomMetric] = useState<PlannedMetricView>('tss');
  const [garminEmail, setGarminEmail] = useState('');
  const [garminPassword, setGarminPassword] = useState('');

  const [result, setResult] = useState<string | null>(null);
  const [customResult, setCustomResult] = useState<string | null>(null);
  const [garminCredResult, setGarminCredResult] = useState<string | null>(null);
  const [editingCustomKey, setEditingCustomKey] = useState<string | null>(null);
  const [editingCustomText, setEditingCustomText] = useState('');
  const [extractLogs, setExtractLogs] = useState<string[]>([]);
  const lastProgressLogCountRef = useRef(0);

  const stamp = () => `[${new Date().toLocaleTimeString()}]`;
  const safeCount = (counts: Record<string, number> | null | undefined, key: string) => Number(counts?.[key] ?? 0);

  const comprehensiveMutation = useMutation({
    mutationFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      setExtractLogs([]);
      lastProgressLogCountRef.current = 0;
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
      const latest = await statusQuery.refetch();
      const counts = latest.data?.counts ?? {};
      setResult(`Comprehensive extract complete: ${response.summary}`);
      setExtractLogs((previous) => [
        ...previous,
        `${stamp()} Final counts: activities=${safeCount(counts, 'activities')}, details=${safeCount(counts, 'activity_details')}, splits=${safeCount(counts, 'activity_splits')}, sleep=${safeCount(counts, 'sleep_daily')}, wellness=${safeCount(counts, 'wellness_daily')}`,
        ...response.errors.map((error) => `[error] ${error}`),
      ]);
    },
    onError: (error) => {
      setResult(error instanceof Error ? error.message : 'Comprehensive extract failed');
      setExtractLogs((previous) => [
        ...previous,
        `${stamp()} Failed: ${error instanceof Error ? error.message : 'Comprehensive extract failed'}`,
      ]);
    },
  });

  useEffect(() => {
    if (!comprehensiveMutation.isPending) return undefined;
    let busy = false;
    const interval = window.setInterval(() => {
      if (busy) return;
      busy = true;
      void statusQuery.refetch().then((snapshot) => {
        const progress = snapshot.data?.extract_progress;
        if (!progress) return;

        const currentLogCount = Number(progress.log_count ?? 0);
        const previousLogCount = Number(lastProgressLogCountRef.current ?? 0);
        if (currentLogCount > previousLogCount) {
          const delta = currentLogCount - previousLogCount;
          const lines = Array.isArray(progress.logs) ? progress.logs : [];
          const appended = delta <= lines.length ? lines.slice(lines.length - delta) : lines;
          if (appended.length > 0) {
            setExtractLogs((prior) => [...prior, ...appended]);
          }
          lastProgressLogCountRef.current = currentLogCount;
        }
      }).finally(() => {
        busy = false;
      });
    }, 2500);
    return () => window.clearInterval(interval);
  }, [comprehensiveMutation.isPending, statusQuery]);

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

  const customUpdateMutation = useMutation({
    mutationFn: async ({ dayUtc, lineNo, activityText }: { dayUtc: string; lineNo: number; activityText: string }) => {
      if (!session?.token) throw new Error('Missing auth token');
      return updateCustomActivityWorkout({
        token: session.token,
        owner: profile?.owner,
        dayUtc,
        lineNo,
        activityText,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['custom-activities'] });
      await queryClient.invalidateQueries({ queryKey: ['data-extract-status'] });
      setEditingCustomKey(null);
      setEditingCustomText('');
    },
    onError: (error) => {
      setCustomResult(error instanceof Error ? error.message : 'Unable to update custom activity.');
    },
  });

  const setGarminCredsMutation = useMutation({
    mutationFn: async ({ email, password }: { email: string; password: string }) => {
      if (!session?.token) throw new Error('Missing auth token');
      return setGarminCredentials({
        token: session.token,
        owner: profile?.owner,
        payload: { email, password },
      });
    },
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ['data-extract-status'] });
      setGarminCredResult(response.message);
      if (response.source === 'session' || response.source === 'missing') {
        setGarminPassword('');
      }
    },
    onError: (error) => {
      setGarminCredResult(error instanceof Error ? error.message : 'Unable to update Garmin credentials.');
    },
  });

  const customWeeks = customActivitiesQuery.data?.weeks ?? [];
  const selectedCustomWeek = useMemo(() => {
    if (customWeeks.length === 0) return null;
    if (!customSelectedWeek) return customWeeks[0];
    return customWeeks.find((week) => week.week_start === customSelectedWeek) ?? customWeeks[0];
  }, [customSelectedWeek, customWeeks]);

  const customRowsForWeek = useMemo(() => {
    if (!selectedCustomWeek) return [];
    const start = new Date(`${selectedCustomWeek.week_start}T00:00:00`);
    const end = new Date(`${selectedCustomWeek.week_end}T23:59:59`);
    return (customActivitiesQuery.data?.rows ?? []).filter((row) => {
      const day = new Date(`${row.day_utc}T12:00:00`);
      return day >= start && day <= end;
    });
  }, [customActivitiesQuery.data?.rows, selectedCustomWeek]);

  const customWeekChartRows = useMemo(() => {
    if (!selectedCustomWeek) return [];
    const start = new Date(`${selectedCustomWeek.week_start}T00:00:00`);
    return Array.from({ length: 7 }).map((_, index) => {
      const day = new Date(start);
      day.setDate(start.getDate() + index);
      const dayIso = day.toISOString().slice(0, 10);
      const total = customRowsForWeek
        .filter((row) => row.day_utc === dayIso)
        .reduce((sum, row) => sum + Number(row[customMetric] ?? 0), 0);
      const tssBasis = customRowsForWeek
        .filter((row) => row.day_utc === dayIso)
        .reduce((sum, row) => sum + Number(row.tss ?? 0), 0);
      const dayLabel = new Intl.DateTimeFormat('en-US', { weekday: 'short', day: 'numeric', month: 'short' }).format(day);
      return { dayLabel, value: total, tssBasis };
    });
  }, [customMetric, customRowsForWeek, selectedCustomWeek]);

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
  const isAdmin = session?.role === 'admin';

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Data Extract</h1>
      </div>

      <Card className={surfaceClassName}>
        <CardContent className="space-y-4 p-4">
          <p className="text-sm font-medium">Comprehensive Garmin Extract</p>
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-full sm:w-[220px]">
              <p className="mb-1 text-xs text-muted-foreground">Start day</p>
              <input
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                type="date"
                max={todayIso()}
                value={startDay}
                onChange={(event) => setStartDay(event.target.value)}
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <label className="inline-flex h-9 items-center gap-2 rounded-md border border-input/80 bg-background/30 px-3 text-xs text-foreground">
                <input
                  className="h-3.5 w-3.5 accent-blue-500"
                  type="checkbox"
                  checked={incrementalOnly}
                  onChange={(event) => setIncrementalOnly(event.target.checked)}
                />
                Incremental only
              </label>
              <label className="inline-flex h-9 items-center gap-2 rounded-md border border-input/80 bg-background/30 px-3 text-xs text-foreground">
                <input
                  className="h-3.5 w-3.5 accent-blue-500"
                  type="checkbox"
                  checked={includeDetails}
                  onChange={(event) => setIncludeDetails(event.target.checked)}
                />
                Include details
              </label>
              <label className="inline-flex h-9 items-center gap-2 rounded-md border border-input/80 bg-background/30 px-3 text-xs text-foreground">
                <input
                  className="h-3.5 w-3.5 accent-blue-500"
                  type="checkbox"
                  checked={includeWellness}
                  onChange={(event) => setIncludeWellness(event.target.checked)}
                />
                Include sleep + wellness
              </label>
            </div>
          </div>
          <div className="flex items-center justify-end">
            <Button
              className="h-9 px-4"
              onClick={() => comprehensiveMutation.mutate()}
              disabled={comprehensiveMutation.isPending}
            >
              {comprehensiveMutation.isPending ? 'Running extract...' : 'Run comprehensive extract'}
            </Button>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/15 p-2">
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
            <div className="max-h-44 overflow-auto rounded-xl border border-white/10 bg-black/20 p-2 font-mono text-xs">
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

      <Card className={surfaceClassName}>
        <CardContent className="space-y-3 p-4">
          <p className="text-sm font-medium">Garmin Credentials</p>
          {isAdmin ? (
            <>
              <p className="text-xs text-muted-foreground">
                Admin account uses server environment credentials (<code>GARMIN_EMAIL</code> / <code>GARMIN_PASSWORD</code>).
              </p>
              <p className="text-xs text-muted-foreground">
                Current source: <span className="font-medium text-foreground">{status?.garmin_credentials_source ?? 'missing'}</span>
              </p>
            </>
          ) : (
            <>
              <p className="text-xs text-muted-foreground">
                Credentials are kept in backend memory only for this user session. They are not saved to the database and will be cleared on backend restart.
              </p>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Garmin email</p>
                  <Input
                    value={garminEmail}
                    onChange={(event) => setGarminEmail(event.target.value)}
                    placeholder="you@example.com"
                    autoComplete="username"
                  />
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Garmin password</p>
                  <Input
                    type="password"
                    value={garminPassword}
                    onChange={(event) => setGarminPassword(event.target.value)}
                    placeholder="••••••••"
                    autoComplete="current-password"
                  />
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  onClick={() => setGarminCredsMutation.mutate({ email: garminEmail.trim(), password: garminPassword })}
                  disabled={setGarminCredsMutation.isPending || !garminEmail.trim() || !garminPassword}
                >
                  {setGarminCredsMutation.isPending ? 'Saving...' : 'Save session credentials'}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setGarminCredsMutation.mutate({ email: '', password: '' })}
                  disabled={setGarminCredsMutation.isPending}
                >
                  Clear
                </Button>
                <p className="text-xs text-muted-foreground">
                  Active source: <span className="font-medium text-foreground">{status?.garmin_credentials_source ?? 'missing'}</span>
                </p>
              </div>
              {garminCredResult ? <p className="text-xs text-muted-foreground">{garminCredResult}</p> : null}
            </>
          )}
        </CardContent>
      </Card>

      {result ? <p className="text-sm text-muted-foreground">{result}</p> : null}

      <Card className={surfaceClassName}>
        <CardContent className="space-y-4 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.08),transparent_38%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] p-5">
          <div className="space-y-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-200/80">Add Custom Activity</p>
            <p className="text-sm text-muted-foreground">
              Use <code>[date]:[activity]</code>. Date formats like <code>3Mar26</code>, <code>2026-03-26</code>, or <code>26/03/2026</code>.
              You can add multiple entries separated by new line, <code>;</code>, or <code>,</code>.
            </p>
          </div>
          <textarea
            className="min-h-[120px] w-full rounded-xl border border-white/10 bg-black/20 px-3 py-3 text-sm text-foreground outline-none transition focus:border-sky-300/40 focus:ring-2 focus:ring-sky-300/20"
            value={customEntryText}
            onChange={(event) => setCustomEntryText(event.target.value)}
            placeholder="e.g. 3Mar26: 80min elliptical @140bpm; 2026-03-26: 10min run @4:50 + 5x6min @3:40/km"
          />
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">This keeps the existing custom-activity save flow, just with the newer composer styling.</p>
            <div className="flex items-center gap-2">
              <Button onClick={() => customIngestMutation.mutate()} disabled={customIngestMutation.isPending || !customEntryText.trim()}>
                {customIngestMutation.isPending ? 'Saving...' : 'Save custom entry'}
              </Button>
              {customResult ? <p className="text-xs text-muted-foreground">{customResult}</p> : null}
            </div>
          </div>

          {customWeeks.length > 0 ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Select
                  value={selectedCustomWeek?.week_start ?? ''}
                  onValueChange={(value) => setCustomSelectedWeek(value)}
                >
                  <SelectTrigger className="w-[220px]">
                    <SelectValue placeholder="Select week" />
                  </SelectTrigger>
                  <SelectContent>
                    {customWeeks.map((week) => (
                      <SelectItem key={week.week_start} value={week.week_start}>
                        {week.week_start} - {week.week_end}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <PlannedMetricSelector value={customMetric} onValueChange={setCustomMetric} />
              </div>

              {selectedCustomWeek ? (
                <div className="rounded-xl border border-white/10 bg-black/15 p-2 text-xs">
                  <p className="text-muted-foreground">
                    {selectedCustomWeek.week_start} - {selectedCustomWeek.week_end}
                  </p>
                  <p className="font-semibold">{selectedCustomWeek.custom_activities} activities</p>
                  <p className="text-muted-foreground">
                    TSS {Math.round(selectedCustomWeek.tss)} · rTSS {Math.round(selectedCustomWeek.rtss)} · Dist{' '}
                    {Math.round(selectedCustomWeek.distance_eqv_km)} kmeq
                  </p>
                </div>
              ) : null}

              <PlannedWeekChart data={customWeekChartRows} metric={customMetric} />
            </>
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
                {customRowsForWeek.map((row) => (
                  <tr key={`${row.day_utc}-${row.line_no}`} className="border-t">
                    <td className="px-2 py-2">{row.day_utc}</td>
                    <td className="px-2 py-2">{row.activity}</td>
                    <td className="px-2 py-2">
                      {editingCustomKey === `${row.day_utc}-${row.line_no}` ? (
                        <textarea
                          className="min-h-[68px] w-full rounded-md border border-input bg-transparent px-2 py-1 text-xs"
                          value={editingCustomText}
                          onChange={(event) => setEditingCustomText(event.target.value)}
                        />
                      ) : (
                        row.activity_text
                      )}
                    </td>
                    <td className="px-2 py-2">{row.pace_label} · IF {Math.round(row.if_proxy_pct)}%</td>
                    <td className="px-2 py-2">TSS {Math.round(row.tss)} · rTSS {Math.round(row.rtss)}</td>
                    <td className="space-x-2 px-2 py-2">
                      {editingCustomKey === `${row.day_utc}-${row.line_no}` ? (
                        <>
                          <Button
                            onClick={() =>
                              customUpdateMutation.mutate({
                                dayUtc: row.day_utc,
                                lineNo: row.line_no,
                                activityText: editingCustomText,
                              })
                            }
                            disabled={customUpdateMutation.isPending || !editingCustomText.trim()}
                          >
                            Save
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => {
                              setEditingCustomKey(null);
                              setEditingCustomText('');
                            }}
                            disabled={customUpdateMutation.isPending}
                          >
                            Cancel
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button
                            variant="outline"
                            onClick={() => {
                              setEditingCustomKey(`${row.day_utc}-${row.line_no}`);
                              setEditingCustomText(row.activity_text);
                            }}
                            disabled={customDeleteMutation.isPending || customUpdateMutation.isPending}
                          >
                            Edit
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => customDeleteMutation.mutate({ dayUtc: row.day_utc, lineNo: row.line_no })}
                            disabled={customDeleteMutation.isPending || customUpdateMutation.isPending}
                          >
                            Delete
                          </Button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
                {!customActivitiesQuery.isLoading && customRowsForWeek.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-2 py-3 text-center text-xs text-muted-foreground">
                      No custom activities in the selected week.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3 p-3 text-sm">
          <div className="grid gap-x-3 gap-y-1 text-xs md:grid-cols-2">
            <p className="truncate"><span className="text-muted-foreground">DB:</span> {status?.db_path}</p>
            <p><span className="text-muted-foreground">Garmin creds:</span> {status?.garmin_credentials_available ? 'available' : 'missing'}</p>
            <p className="truncate"><span className="text-muted-foreground">Import dir:</span> {status?.import_dir}</p>
            {status?.last_sync ? (
              <p className="truncate">
                <span className="text-muted-foreground">Last sync:</span> {status.last_sync.sync_time_utc} | {status.last_sync.source} | {status.last_sync.success ? 'success' : 'failed'}
              </p>
            ) : (
              <p className="text-muted-foreground">No sync has been run yet.</p>
            )}
          </div>
          <div className="grid gap-1.5 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {Object.entries(status?.counts ?? {}).map(([key, value]) => (
              <div key={key} className="rounded border border-border/70 bg-muted/20 px-2 py-1.5 text-xs">
                <p className="truncate text-muted-foreground">{key}</p>
                <p className="text-sm font-semibold leading-5 text-foreground">{value}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
