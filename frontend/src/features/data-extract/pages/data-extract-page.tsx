import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { CompactDateInput } from '@/components/ui/compact-date-input';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  SecondaryPageHeader,
  SecondaryPageSectionCard,
  secondaryPageActionButtonClassName,
  secondaryPageFieldLabelClassName,
  secondaryPageInputClassName,
  secondaryPageInsetClassName,
  secondaryPageMutedInsetClassName,
  secondaryPageTextAreaClassName,
} from '@/components/ui/secondary-page';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { useCustomActivitiesQuery } from '@/features/custom-activities/hooks/use-custom-activities-query';
import {
  deleteCustomActivity,
  ingestCustomActivities,
  updateCustomActivityWorkout,
} from '@/features/custom-activities/services/custom-activities-api';
import { useDataExtractStatusQuery } from '@/features/data-extract/hooks/use-data-extract-status';
import {
  disconnectGarminOAuth,
  resetGarminAuth,
  runComprehensiveExtract,
  setGarminCredentials,
  startGarminOAuth,
} from '@/features/data-extract/services/data-extract-api';
import { PlannedMetricSelector } from '@/features/plan-activities/components/planned-metric-selector';
import { PlannedWeekChart } from '@/features/plan-activities/components/planned-week-chart';
import type { PlannedMetricView } from '@/features/plan-activities/types/plan-activities';
import { queryClient } from '@/lib/query-client';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

function startDayFromPreset(monthsBack: number): string {
  const now = new Date();
  const start = new Date(now);
  start.setMonth(start.getMonth() - monthsBack);
  return `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
}

export function DataExtractPage(): JSX.Element {
  const { session, profile } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const statusQuery = useDataExtractStatusQuery();
  const customActivitiesQuery = useCustomActivitiesQuery();

  const [extractStartDay, setExtractStartDay] = useState(() => startDayFromPreset(1));
  const [incrementalOnly, setIncrementalOnly] = useState(true);
  const [includeDetails, setIncludeDetails] = useState(true);
  const [includeWellness, setIncludeWellness] = useState(true);
  const [customEntryText, setCustomEntryText] = useState('');
  const [customSelectedWeek, setCustomSelectedWeek] = useState('');
  const [customMetric, setCustomMetric] = useState<PlannedMetricView>('tss');
  const [garminEmail, setGarminEmail] = useState('');
  const [garminPassword, setGarminPassword] = useState('');

  const [result, setResult] = useState<string | null>(null);
  const [customResult, setCustomResult] = useState<string | null>(null);
  const [garminCredResult, setGarminCredResult] = useState<string | null>(null);
  const [garminResetResult, setGarminResetResult] = useState<string | null>(null);
  const [garminOAuthResult, setGarminOAuthResult] = useState<string | null>(null);
  const [customEditValues, setCustomEditValues] = useState<Record<string, string>>({});
  const [extractLogs, setExtractLogs] = useState<string[]>([]);
  const lastProgressLogCountRef = useRef(0);
  const lastFinishedAtRef = useRef<string | null>(null);

  const stamp = () => `[${new Date().toLocaleTimeString()}]`;
  const comprehensiveMutation = useMutation({
    mutationFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      setResult(null);
      setExtractLogs([]);
      lastProgressLogCountRef.current = 0;
      lastFinishedAtRef.current = null;
      return runComprehensiveExtract({
        token: session.token,
        owner: profile?.owner,
        payload: {
          start_day: extractStartDay,
          incremental_only: incrementalOnly,
          include_details: includeDetails,
          include_wellness: includeWellness,
          verify_raw_integrity: false,
        },
      });
    },
    onMutate: () => {
      setResult(`Starting Garmin extract from ${extractStartDay}...`);
    },
    onSuccess: async (response) => {
      setResult(
        `${response.summary} Requested ${response.requested_start_day}; fetching ${response.computed_start_day} to ${response.end_day}.`,
      );
      await queryClient.invalidateQueries({ queryKey: ['data-extract-status'] });
      const latest = await statusQuery.refetch();
      const progress = latest.data?.extract_progress;
      lastProgressLogCountRef.current = Number(progress?.log_count ?? 0);
      const nextLogs = Array.isArray(progress?.logs) ? progress.logs : [];
      setExtractLogs(nextLogs.length > 0 ? nextLogs : [`${stamp()} ${response.summary}`]);
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
    const progress = statusQuery.data?.extract_progress;
    if (!progress) return;

    const currentLogCount = Number(progress.log_count ?? 0);
    const previousLogCount = Number(lastProgressLogCountRef.current ?? 0);
    const lines = Array.isArray(progress.logs) ? progress.logs : [];

    if (previousLogCount === 0 || currentLogCount < previousLogCount) {
      setExtractLogs(lines);
      lastProgressLogCountRef.current = currentLogCount;
    } else if (currentLogCount > previousLogCount) {
      const delta = currentLogCount - previousLogCount;
      const appended = delta <= lines.length ? lines.slice(lines.length - delta) : lines;
      if (appended.length > 0) {
        setExtractLogs((prior) => [...prior, ...appended]);
      }
      lastProgressLogCountRef.current = currentLogCount;
    }

    if (!progress.running && progress.finished_at && lastFinishedAtRef.current !== progress.finished_at) {
      lastFinishedAtRef.current = progress.finished_at;
    }
  }, [statusQuery.data]);

  useEffect(() => {
    const search = new URLSearchParams(location.search);
    const oauthStatus = search.get('garmin_oauth');
    const oauthMessage = search.get('garmin_oauth_message');
    if (!oauthStatus && !oauthMessage) return;
    setGarminOAuthResult(oauthMessage ?? (oauthStatus === 'success' ? 'Garmin OAuth connected.' : 'Garmin OAuth failed.'));
    const nextSearch = new URLSearchParams(location.search);
    nextSearch.delete('garmin_oauth');
    nextSearch.delete('garmin_oauth_message');
    navigate(
      {
        pathname: location.pathname,
        search: nextSearch.toString() ? `?${nextSearch.toString()}` : '',
      },
      { replace: true },
    );
  }, [location.pathname, location.search, navigate]);

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
      if (response.errors.length > 0 && response.saved_count <= 0) {
        setCustomResult(response.errors[0] ?? 'Unable to save custom activities.');
      } else if (response.errors.length > 0) {
        setCustomResult(`Saved ${response.saved_count} to ${profile?.owner ?? '-'}. Some entries were skipped.`);
      } else {
        setCustomResult(`Saved ${response.saved_count} custom activit${response.saved_count === 1 ? 'y' : 'ies'} to ${profile?.owner ?? '-'}.`);
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

  const startGarminOAuthMutation = useMutation({
    mutationFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      return startGarminOAuth({
        token: session.token,
        owner: profile?.owner,
      });
    },
    onSuccess: (response) => {
      window.location.assign(response.authorization_url);
    },
    onError: (error) => {
      setGarminOAuthResult(error instanceof Error ? error.message : 'Unable to start Garmin OAuth.');
    },
  });

  const disconnectGarminOAuthMutation = useMutation({
    mutationFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      return disconnectGarminOAuth({
        token: session.token,
        owner: profile?.owner,
      });
    },
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ['data-extract-status'] });
      setGarminOAuthResult(response.message);
    },
    onError: (error) => {
      setGarminOAuthResult(error instanceof Error ? error.message : 'Unable to disconnect Garmin OAuth.');
    },
  });

  const resetGarminAuthMutation = useMutation({
    mutationFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      return resetGarminAuth({
        token: session.token,
        owner: profile?.owner,
      });
    },
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ['data-extract-status'] });
      setGarminPassword('');
      setGarminResetResult(
        response.garmin_rate_limit?.active
          ? `${response.message}. Garmin rate limit remains active until ${response.garmin_rate_limit.until_utc ?? 'later'}.`
          : response.message,
      );
    },
    onError: (error) => {
      setGarminResetResult(error instanceof Error ? error.message : 'Unable to reset Garmin auth.');
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

  useEffect(() => {
    const next: Record<string, string> = {};
    customRowsForWeek.forEach((row) => {
      next[`${row.day_utc}-${row.line_no}`] = row.activity_text;
    });
    setCustomEditValues(next);
  }, [customRowsForWeek]);

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
  const isAdminOwnScope = isAdmin && profile?.owner === session?.user;
  const extractRunning = Boolean(status?.extract_progress?.running);
  const garminOauthConnected = Boolean(status?.garmin_oauth?.connected);
  const garminCapabilities = status?.garmin_capabilities;
  const legacyFallbackAvailable = Boolean(status?.garmin_credentials_available);
  const oauthBlocksExtract =
    status?.garmin_connection_mode === 'oauth'
    && !legacyFallbackAvailable
    && (!garminCapabilities?.activities || (includeWellness && !garminCapabilities?.wellness) || !garminCapabilities?.comprehensive);

  return (
    <section className="space-y-4 sm:space-y-6">
      <SecondaryPageHeader
        title="Data Extract"
        description={`Sync Garmin data, manage credentials, and review the current import status for ${profile?.owner ?? '-'}.`}
      />

      <SecondaryPageSectionCard contentClassName="space-y-3 sm:space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Garmin Sync</h2>

          <div className="grid gap-2 rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.03),rgba(255,255,255,0.01))] p-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] sm:flex sm:flex-wrap sm:items-center sm:gap-2 sm:p-3">
            <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2 sm:contents">
            <div className="min-w-[180px] flex-1 sm:max-w-[220px]">
              <CompactDateInput
                value={extractStartDay}
                onChange={setExtractStartDay}
                mobileInputClassName="h-9 rounded-xl border-white/10 bg-black/10 px-3 text-[13px]"
                desktopInputClassName="h-10 rounded-xl"
                buttonClassName="h-9 w-9 rounded-xl"
              />
            </div>
            <Button
              type="button"
              className={`${secondaryPageActionButtonClassName} relative z-10 w-full rounded-xl sm:w-auto`}
              onClick={() => comprehensiveMutation.mutate()}
              disabled={comprehensiveMutation.isPending || extractRunning || oauthBlocksExtract}
            >
              {extractRunning || comprehensiveMutation.isPending ? 'Running...' : 'Run extract'}
            </Button>
            </div>
            <div className="grid grid-cols-3 gap-2 sm:flex sm:flex-wrap sm:items-center sm:gap-2">
            <label className={`inline-flex h-9 items-center justify-center gap-1.5 rounded-xl px-2.5 text-[11px] font-semibold transition sm:h-10 sm:px-3.5 sm:text-xs ${
              includeDetails
                ? 'bg-[linear-gradient(180deg,rgba(56,189,248,0.22),rgba(14,165,233,0.08))] text-sky-100 ring-1 ring-sky-300/26 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]'
                : 'bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.015))] text-slate-200/84 ring-1 ring-white/7 hover:bg-white/6'
            }`}>
                <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${includeDetails ? 'bg-sky-200 shadow-[0_0_0_3px_rgba(125,211,252,0.12)]' : 'bg-slate-500/70'}`} />
                <input
                  className="sr-only"
                  type="checkbox"
                  checked={includeDetails}
                  onChange={(event) => setIncludeDetails(event.target.checked)}
                />
                Activities
              </label>
            <label className={`inline-flex h-9 items-center justify-center gap-1.5 rounded-xl px-2.5 text-[11px] font-semibold transition sm:h-10 sm:px-3.5 sm:text-xs ${
              includeWellness
                ? 'bg-[linear-gradient(180deg,rgba(56,189,248,0.22),rgba(14,165,233,0.08))] text-sky-100 ring-1 ring-sky-300/26 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]'
                : 'bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.015))] text-slate-200/84 ring-1 ring-white/7 hover:bg-white/6'
            }`}>
                <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${includeWellness ? 'bg-sky-200 shadow-[0_0_0_3px_rgba(125,211,252,0.12)]' : 'bg-slate-500/70'}`} />
                <input
                  className="sr-only"
                  type="checkbox"
                  checked={includeWellness}
                  onChange={(event) => setIncludeWellness(event.target.checked)}
                />
                Wellness
              </label>
            <label className={`inline-flex h-9 items-center justify-center gap-1.5 rounded-xl px-2.5 text-[11px] font-semibold transition sm:h-10 sm:px-3.5 sm:text-xs ${
              incrementalOnly
                ? 'bg-[linear-gradient(180deg,rgba(56,189,248,0.22),rgba(14,165,233,0.08))] text-sky-100 ring-1 ring-sky-300/26 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]'
                : 'bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.015))] text-slate-200/84 ring-1 ring-white/7 hover:bg-white/6'
            }`}>
                <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${incrementalOnly ? 'bg-sky-200 shadow-[0_0_0_3px_rgba(125,211,252,0.12)]' : 'bg-slate-500/70'}`} />
                <input
                  className="sr-only"
                  type="checkbox"
                  checked={incrementalOnly}
                  onChange={(event) => setIncrementalOnly(event.target.checked)}
                />
                Incremental
              </label>
            </div>
          </div>
          {result ? <p className="text-sm text-slate-200/82">{result}</p> : null}
          {oauthBlocksExtract ? (
            <p className="text-xs text-amber-200/84">
              {garminCapabilities?.reason ?? 'Garmin OAuth is connected, but extract endpoints are not configured for this deployment.'}
            </p>
          ) : null}
          <div className={`${secondaryPageInsetClassName} p-2`}>
            <div className="mb-1 flex items-center justify-between gap-2">
              <p className="text-xs font-medium text-muted-foreground">Extraction logs</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setExtractLogs([])}
                disabled={extractRunning || comprehensiveMutation.isPending || extractLogs.length === 0}
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
      </SecondaryPageSectionCard>

      {!isAdmin ? (
        <SecondaryPageSectionCard contentClassName="space-y-3 p-3 sm:p-4">
          <h2 className="text-lg font-semibold text-foreground">Garmin OAuth</h2>
          <div className={`${secondaryPageMutedInsetClassName} space-y-2 p-3`}>
            <p className="text-xs text-muted-foreground">
              Status:{' '}
              <span className="font-medium text-foreground">
                {garminOauthConnected ? `Connected${status?.garmin_oauth?.account_email ? ` as ${status.garmin_oauth.account_email}` : ''}` : 'Not connected'}
              </span>
            </p>
            <p className="text-xs text-muted-foreground">
              Active source: <span className="font-medium text-foreground">{status?.garmin_connection_mode ?? 'missing'}</span>
            </p>
            {status?.garmin_oauth?.expires_at ? (
              <p className="text-xs text-muted-foreground">Token expiry: {status.garmin_oauth.expires_at}</p>
            ) : null}
            {status?.garmin_oauth?.scopes?.length ? (
              <p className="text-xs text-muted-foreground">Scopes: {status.garmin_oauth.scopes.join(', ')}</p>
            ) : null}
            {garminCapabilities?.reason ? (
              <p className="text-xs text-muted-foreground">{garminCapabilities.reason}</p>
            ) : null}
          </div>
          <div className="flex flex-col items-start gap-2 sm:flex-row sm:flex-wrap sm:items-center">
            <Button
              className={`${secondaryPageActionButtonClassName} w-full sm:w-auto`}
              onClick={() => startGarminOAuthMutation.mutate()}
              disabled={startGarminOAuthMutation.isPending || garminOauthConnected}
            >
              {startGarminOAuthMutation.isPending ? 'Redirecting...' : 'Connect Garmin'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => disconnectGarminOAuthMutation.mutate()}
              disabled={disconnectGarminOAuthMutation.isPending || !garminOauthConnected}
            >
              {disconnectGarminOAuthMutation.isPending ? 'Disconnecting...' : 'Disconnect Garmin'}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            OAuth is preferred when available. Session credentials below remain the compatibility fallback when OAuth extract support is unavailable in this deployment.
          </p>
          {garminOAuthResult ? <p className="text-xs text-muted-foreground">{garminOAuthResult}</p> : null}
        </SecondaryPageSectionCard>
      ) : null}

      <SecondaryPageSectionCard contentClassName="space-y-3 p-3 sm:p-4">
          <h2 className="text-lg font-semibold text-foreground">Garmin Credentials</h2>
          {isAdminOwnScope ? (
            <>
              <p className="text-xs text-muted-foreground">
                Current source: <span className="font-medium text-foreground">{status?.garmin_credentials_source ?? 'missing'}</span>
              </p>
              <div className="flex flex-col items-start gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => resetGarminAuthMutation.mutate()}
                  disabled={resetGarminAuthMutation.isPending}
                >
                  {resetGarminAuthMutation.isPending ? 'Resetting...' : 'Reset Garmin auth'}
                </Button>
                <p className="text-xs text-muted-foreground">
                  Clears cached Garmin session/tokens for this backend process.
                </p>
              </div>
              {garminResetResult ? <p className="text-xs text-muted-foreground">{garminResetResult}</p> : null}
            </>
          ) : (
            <>
              <p className="text-xs text-muted-foreground">
                {isAdmin
                  ? `When viewing ${profile?.owner ?? 'another owner'}, provide that user's Garmin credentials here. Running extract will ingest into ${profile?.owner ?? 'that'} database, and these credentials stay in memory only.`
                  : 'Credentials are kept in backend memory only for this user session. They are not saved to the database and will be cleared on backend restart.'}
              </p>
              <div className="grid gap-2 sm:gap-3 md:grid-cols-2">
                <div className="space-y-1">
                  <Label htmlFor="garmin-email" className={secondaryPageFieldLabelClassName}>Garmin email</Label>
                  <Input
                    id="garmin-email"
                    className={secondaryPageInputClassName}
                    value={garminEmail}
                    onChange={(event) => setGarminEmail(event.target.value)}
                    placeholder="you@example.com"
                    autoComplete="username"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="garmin-password" className={secondaryPageFieldLabelClassName}>Garmin password</Label>
                  <Input
                    id="garmin-password"
                    className={secondaryPageInputClassName}
                    type="password"
                    value={garminPassword}
                    onChange={(event) => setGarminPassword(event.target.value)}
                    placeholder="••••••••"
                    autoComplete="current-password"
                  />
                </div>
              </div>
              <div className="flex flex-col items-start gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                <Button
                  className={`${secondaryPageActionButtonClassName} w-full sm:w-auto`}
                  onClick={() => setGarminCredsMutation.mutate({ email: garminEmail.trim(), password: garminPassword })}
                  disabled={setGarminCredsMutation.isPending || !garminEmail.trim() || !garminPassword}
                >
                  {setGarminCredsMutation.isPending ? 'Saving...' : isAdmin ? 'Save owner credentials' : 'Save session credentials'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setGarminCredsMutation.mutate({ email: '', password: '' })}
                  disabled={setGarminCredsMutation.isPending}
                >
                  Clear
                </Button>
                {isAdmin ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => resetGarminAuthMutation.mutate()}
                    disabled={resetGarminAuthMutation.isPending}
                  >
                    {resetGarminAuthMutation.isPending ? 'Resetting...' : 'Reset Garmin auth'}
                  </Button>
                ) : null}
                <p className="text-xs text-muted-foreground">
                  Active source: <span className="font-medium text-foreground">{status?.garmin_connection_mode ?? status?.garmin_credentials_source ?? 'missing'}</span>
                </p>
              </div>
              {garminCredResult ? <p className="text-xs text-muted-foreground">{garminCredResult}</p> : null}
              {garminResetResult ? <p className="text-xs text-muted-foreground">{garminResetResult}</p> : null}
            </>
          )}
      </SecondaryPageSectionCard>

      <SecondaryPageSectionCard contentClassName="space-y-3 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.08),transparent_38%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] sm:space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Add Custom Activity</h2>
          <Label htmlFor="custom-activity-entry" className={secondaryPageFieldLabelClassName}>
            Activity input
          </Label>
          <textarea
            id="custom-activity-entry"
            className={`min-h-[104px] ${secondaryPageTextAreaClassName} sm:min-h-[120px]`}
            value={customEntryText}
            onChange={(event) => setCustomEntryText(event.target.value)}
            placeholder="e.g. 3Mar26: 80min elliptical @140bpm; 2026-03-26: 10min run @4:50 + 5x6min @3:40/km"
          />
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
            <p className="text-xs text-muted-foreground">This keeps the existing custom-activity save flow, just with the newer composer styling.</p>
            <div className="flex w-full flex-col items-stretch gap-2 sm:w-auto sm:flex-row sm:items-center">
              <Button
                className={`${secondaryPageActionButtonClassName} w-full sm:w-auto`}
                onClick={() => customIngestMutation.mutate()}
                disabled={customIngestMutation.isPending || !customEntryText.trim()}
              >
                {customIngestMutation.isPending ? 'Saving...' : 'Save'}
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
                  <SelectTrigger className="h-9 w-full sm:h-10 sm:w-[220px]">
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
                <div className={`${secondaryPageInsetClassName} p-2 text-xs`}>
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

          {isAdmin ? (
            <div className="overflow-x-auto rounded-2xl pb-1">
              <table className="min-w-[940px] w-full table-fixed text-sm">
                <colgroup>
                  <col className="w-[108px]" />
                  <col className="w-[120px]" />
                  <col className="w-auto" />
                  <col className="w-[82px]" />
                  <col className="w-[82px]" />
                  <col className="w-[104px]" />
                  <col className="w-[74px]" />
                  <col className="w-[148px]" />
                </colgroup>
                <thead className="bg-white/5 text-left text-slate-300/72">
                  <tr>
                    <th className="px-2 py-2 text-left sm:px-3">Day</th>
                    <th className="px-2 py-2 text-left sm:px-3">Activity</th>
                    <th className="px-2 py-2 text-left sm:px-3">Workout</th>
                    <th className="px-2 py-2 text-right sm:px-3">TSS</th>
                    <th className="px-2 py-2 text-right sm:px-3">rTSS</th>
                    <th className="px-2 py-2 text-right sm:px-3">Dist Eqv</th>
                    <th className="px-2 py-2 text-right sm:px-3">IF</th>
                    <th className="px-2 py-2 text-center sm:px-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {customRowsForWeek.map((row) => {
                    const rowKey = `${row.day_utc}-${row.line_no}`;
                    return (
                    <tr key={rowKey} className="border-t border-white/10">
                      <td className="px-2 py-2 sm:px-3">{row.day_utc}</td>
                      <td className="px-2 py-2 sm:px-3">{row.activity}</td>
                      <td className="px-2 py-2 sm:px-3">
                        <input
                          className="min-w-[240px] w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-foreground outline-none transition focus:border-sky-300/40 focus:ring-2 focus:ring-sky-300/20"
                          value={customEditValues[rowKey] ?? ''}
                          onChange={(event) =>
                            setCustomEditValues((previous) => ({ ...previous, [rowKey]: event.target.value }))
                          }
                        />
                      </td>
                      <td className="px-2 py-2 text-right sm:px-3">{Math.round(row.tss)}</td>
                      <td className="px-2 py-2 text-right sm:px-3">{Math.round(row.rtss)}</td>
                      <td className="px-2 py-2 text-right sm:px-3">{row.distance_eqv_km.toFixed(1)} km</td>
                      <td className="px-2 py-2 text-right sm:px-3">{row.if_proxy_pct.toFixed(0)}%</td>
                      <td className="px-2 py-2 text-right sm:px-3">
                        <div className="flex justify-end gap-1.5">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="px-2.5 text-slate-200 hover:bg-white/10 hover:text-white"
                            onClick={() =>
                              customUpdateMutation.mutate({
                                dayUtc: row.day_utc,
                                lineNo: row.line_no,
                                activityText: customEditValues[rowKey] ?? row.activity_text,
                              })
                            }
                            disabled={customUpdateMutation.isPending || !String(customEditValues[rowKey] ?? '').trim()}
                          >
                            Save
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="px-2.5 text-slate-300 hover:bg-rose-500/12 hover:text-rose-100"
                            onClick={() => customDeleteMutation.mutate({ dayUtc: row.day_utc, lineNo: row.line_no })}
                            disabled={customDeleteMutation.isPending || customUpdateMutation.isPending}
                          >
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )})}
                  {!customActivitiesQuery.isLoading && customRowsForWeek.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-3 py-6 text-center text-sm text-slate-300/60">
                        No custom activities in the selected week.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          ) : null}
      </SecondaryPageSectionCard>

      {isAdmin ? (
        <SecondaryPageSectionCard contentClassName="space-y-3 p-3 text-sm sm:space-y-4 sm:p-4">
            <div className="grid gap-2 rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.03),rgba(255,255,255,0.01))] p-2.5 text-xs md:hidden">
              <div className={`${secondaryPageInsetClassName} px-3 py-2.5`}>
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">DB</p>
                <p className="mt-1 break-all text-slate-200/88">{status?.db_path}</p>
              </div>
              <div className={`${secondaryPageInsetClassName} px-3 py-2.5`}>
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">Garmin Creds</p>
                <p className="mt-1 text-slate-200/88">{status?.garmin_credentials_available ? 'available' : 'missing'}</p>
              </div>
              <div className={`${secondaryPageInsetClassName} px-3 py-2.5`}>
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">Import Dir</p>
                <p className="mt-1 break-all text-slate-200/88">{status?.import_dir}</p>
              </div>
              <div className={`${secondaryPageInsetClassName} px-3 py-2.5`}>
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">Last Sync</p>
                <p className="mt-1 text-slate-200/88">
                  {status?.last_sync
                    ? `${status.last_sync.sync_time_utc} | ${status.last_sync.source} | ${status.last_sync.success ? 'success' : 'failed'}`
                    : 'No sync has been run yet.'}
                </p>
              </div>
            </div>
            <div className="hidden gap-2 rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.03),rgba(255,255,255,0.01))] p-2.5 text-xs sm:gap-3 sm:p-3 md:grid md:grid-cols-2">
              <p className={`truncate ${secondaryPageInsetClassName} px-3 py-2 text-slate-200/88`}>
                <span className="text-slate-300/58">DB:</span> {status?.db_path}
              </p>
              <p className={`${secondaryPageInsetClassName} px-3 py-2 text-slate-200/88`}>
                <span className="text-slate-300/58">Garmin creds:</span> {status?.garmin_credentials_available ? 'available' : 'missing'}
              </p>
              <p className={`truncate ${secondaryPageInsetClassName} px-3 py-2 text-slate-200/88`}>
                <span className="text-slate-300/58">Import dir:</span> {status?.import_dir}
              </p>
              {status?.last_sync ? (
                <p className={`truncate ${secondaryPageInsetClassName} px-3 py-2 text-slate-200/88`}>
                  <span className="text-slate-300/58">Last sync:</span> {status.last_sync.sync_time_utc} | {status.last_sync.source} | {status.last_sync.success ? 'success' : 'failed'}
                </p>
              ) : (
                <p className={`${secondaryPageInsetClassName} px-3 py-2 text-slate-300/60`}>No sync has been run yet.</p>
              )}
            </div>
            <div className="grid gap-2 md:hidden">
              {Object.entries(status?.counts ?? {}).map(([key, value]) => (
                <div
                  key={key}
                  className={`flex items-center justify-between ${secondaryPageMutedInsetClassName} px-3 py-2.5 text-xs shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]`}
                >
                  <p className="pr-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-200/74">{key}</p>
                  <p className="text-sm font-semibold leading-5 text-slate-100">{value}</p>
                </div>
              ))}
            </div>
            <div className="hidden gap-1.5 grid-cols-2 sm:grid-cols-2 md:grid md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {Object.entries(status?.counts ?? {}).map(([key, value]) => (
                <div
                  key={key}
                  className={`${secondaryPageMutedInsetClassName} px-3 py-2 text-xs shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]`}
                >
                  <p className="truncate text-slate-300/58">{key}</p>
                  <p className="text-sm font-semibold leading-5 text-slate-100">{value}</p>
                </div>
              ))}
            </div>
        </SecondaryPageSectionCard>
      ) : null}
    </section>
  );
}
