import { useMutation } from '@tanstack/react-query';
import { Suspense, lazy, startTransition, useEffect, useMemo, useRef, useState } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { QueryShell } from '@/components/ui/query-shell';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { deleteCustomActivity, ingestCustomActivities } from '@/features/custom-activities/services/custom-activities-api';
import { DashboardWeekCard } from '@/features/dashboard/components/dashboard-week-card';
import { useDashboardQuery } from '@/features/dashboard/hooks/use-dashboard-query';
import { getDashboard, toggleActivityInvalid } from '@/features/dashboard/services/dashboard-api';
import { generateActivitySuggestion } from '@/features/dashboard/services/generated-activity-api';
import type { DashboardActivityCard, DashboardResponse } from '@/features/dashboard/types/dashboard';
import { useDataExtractStatusQuery } from '@/features/data-extract/hooks/use-data-extract-status';
import { runComprehensiveExtract } from '@/features/data-extract/services/data-extract-api';
import {
  deletePlannedActivity,
  ingestPlannedActivities,
  setPlannedManualDone,
} from '@/features/plan-activities/services/plan-activities-api';
import { queryClient } from '@/lib/query-client';

const ActivitySplitsDrawer = lazy(async () => ({
  default: (await import('@/features/dashboard/components/activity-splits-drawer')).ActivitySplitsDrawer,
}));

function timeHintFromWorkoutText(workoutText: string): 'AM' | 'PM' | null {
  const match = String(workoutText || '').match(/(^|[^A-Za-z0-9_])(AM|PM)([^A-Za-z0-9_]|$)/i);
  if (!match) return null;
  const hint = String(match[2] || '').toUpperCase();
  return hint === 'AM' || hint === 'PM' ? hint : null;
}

function plannedCardIsVisible(
  dayUtc: string,
  workoutText: string,
  now: Date,
): boolean {
  const day = new Date(`${dayUtc}T00:00:00`);
  if (Number.isNaN(day.getTime())) return true;

  const expiry = new Date(day);
  const hint = timeHintFromWorkoutText(workoutText);
  if (hint === 'AM') {
    expiry.setHours(12, 0, 0, 0);
  } else if (hint === 'PM') {
    expiry.setHours(21, 0, 0, 0);
  } else {
    expiry.setDate(expiry.getDate() + 1);
    expiry.setHours(0, 0, 0, 0);
  }
  return now.getTime() < expiry.getTime();
}

function isTodayOrPast(dayUtc: string): boolean {
  const selected = new Date(`${dayUtc}T00:00:00`);
  if (Number.isNaN(selected.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  selected.setHours(0, 0, 0, 0);
  return selected.getTime() <= today.getTime();
}

function currentWeekStartIso(): string {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const dayOffset = (today.getDay() + 6) % 7;
  today.setDate(today.getDate() - dayOffset);
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatLongDate(dayUtc: string): string {
  const parsed = new Date(`${dayUtc}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return dayUtc;
  return new Intl.DateTimeFormat('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).format(parsed);
}

function startDayFromPreset(monthsBack: number): string {
  const now = new Date();
  const start = new Date(now);
  start.setMonth(start.getMonth() - monthsBack);
  return `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
}

function composerActivityKeyword(activityType: 'running' | 'elliptical' | 'bike'): 'run' | 'elliptical' | 'bike' {
  if (activityType === 'elliptical') return 'elliptical';
  if (activityType === 'bike') return 'bike';
  return 'run';
}

function chunkHasExplicitActivity(text: string): boolean {
  const normalized = String(text || '').toLowerCase();
  return /\btreadmill\b|\brun\b|\bellipt(?:ical)?\b|\bx-?train\b|\bcross(?:\s|-)?train\b|\bbike\b|\bcycl(?:ing)?\b/.test(normalized);
}

function applyComposerActivityFallback(
  workoutText: string,
  activityType: 'running' | 'elliptical' | 'bike',
): string {
  const fallbackActivity = composerActivityKeyword(activityType);
  return String(workoutText || '')
    .split(/(\n|;|,)/)
    .map((entry) => {
      if (entry === '\n' || entry === ';' || entry === ',') return entry;
      const trimmedEntry = entry.trim();
      if (!trimmedEntry) return entry;

      let lastExplicitActivity = '';
      const nextChunks = trimmedEntry.split(/\s*\+\s*/).map((chunk) => {
        const trimmedChunk = chunk.trim();
        if (!trimmedChunk) return trimmedChunk;
        if (chunkHasExplicitActivity(trimmedChunk)) {
          lastExplicitActivity = trimmedChunk;
          return trimmedChunk;
        }
        if (lastExplicitActivity) return trimmedChunk;
        return `${fallbackActivity} ${trimmedChunk}`;
      });

      return nextChunks.join(' + ');
    })
    .join('');
}

export function DashboardPage(): JSX.Element {
  const dashboardPageSize = 4;
  const dashboardYearWindowWeeks = 52;
  const dashboardMaxWeeks = 52;
  const { session, profile } = useAuth();
  const [visibleWeeks, setVisibleWeeks] = useState(dashboardPageSize);
  const [selectedYearWindow, setSelectedYearWindow] = useState('0');
  const [selectedActivityId, setSelectedActivityId] = useState<string | null>(null);
  const [addActivityDayUtc, setAddActivityDayUtc] = useState<string | null>(null);
  const [addActivityText, setAddActivityText] = useState('');
  const [addActivityMode, setAddActivityMode] = useState<'planned' | 'custom'>('planned');
  const [addGeneratedActivityType, setAddGeneratedActivityType] = useState<'running' | 'elliptical' | 'bike'>('running');
  const [lastGeneratedActivityText, setLastGeneratedActivityText] = useState<string>('');
  const [addActivityResult, setAddActivityResult] = useState<string | null>(null);
  const [dashboardReloadResult, setDashboardReloadResult] = useState<string | null>(null);
  const [dashboardReloadQueued, setDashboardReloadQueued] = useState(false);
  const [dashboardReloadSawRunning, setDashboardReloadSawRunning] = useState(false);
  const [undoState, setUndoState] = useState<{
    id: number;
    lane: 'planned' | 'actual';
    dayUtc?: string;
    lineNo?: number;
    slotIndex?: number;
    label: string;
    action: (() => Promise<void>) | null;
    finalize: (() => Promise<void>) | null;
  } | null>(null);
  const [undoVisible, setUndoVisible] = useState(false);
  const weekRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const lastAnchoredWeekRef = useRef<string>('');
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const undoTimerRef = useRef<number | null>(null);
  const undoDismissTimerRef = useRef<number | null>(null);
  const undoStateRef = useRef<{
    id: number;
    lane: 'planned' | 'actual';
    dayUtc?: string;
    lineNo?: number;
    slotIndex?: number;
    label: string;
    action: (() => Promise<void>) | null;
    finalize: (() => Promise<void>) | null;
  } | null>(null);
  const selectedYearWindowIndex = useMemo(() => {
    const parsed = Number(selectedYearWindow);
    if (!Number.isFinite(parsed) || parsed < 0) return 0;
    return parsed;
  }, [selectedYearWindow]);
  const weekOffset = selectedYearWindowIndex * dashboardYearWindowWeeks;
  const query = useDashboardQuery(visibleWeeks, 'all', weekOffset);
  const extractStatusQuery = useDataExtractStatusQuery();
  const userTimeZone = useMemo(() => {
    const profileAny = profile as unknown as Record<string, unknown> | null;
    const tzFromProfile =
      String(profileAny?.timezone || profileAny?.user_timezone || profileAny?.tz || '').trim();
    if (tzFromProfile) return tzFromProfile;
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  }, [profile]);
  const canAddCustomForComposer = useMemo(
    () => Boolean(addActivityDayUtc && isTodayOrPast(addActivityDayUtc)),
    [addActivityDayUtc],
  );
  const composerCurrentWeekStart = useMemo(() => currentWeekStartIso(), []);
  const isBeforeCurrentWeek = useMemo(() => {
    if (!addActivityDayUtc) return false;
    return addActivityDayUtc < composerCurrentWeekStart;
  }, [addActivityDayUtc, composerCurrentWeekStart]);
  const canAddPlannedForComposer = useMemo(
    () => Boolean(addActivityDayUtc) && !isBeforeCurrentWeek,
    [addActivityDayUtc, isBeforeCurrentWeek],
  );

  useEffect(() => {
    if (!addActivityDayUtc) return;
    if (isBeforeCurrentWeek && addActivityMode !== 'custom') {
      setAddActivityMode('custom');
      return;
    }
    if (!canAddCustomForComposer && addActivityMode === 'custom') {
      setAddActivityMode('planned');
    }
  }, [addActivityDayUtc, addActivityMode, canAddCustomForComposer, isBeforeCurrentWeek]);
  useEffect(() => {
    setLastGeneratedActivityText('');
  }, [addActivityDayUtc, addActivityMode, addGeneratedActivityType]);
  const refreshDashboardViews = async () => {
    await Promise.all([
      query.refetch(),
      queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
      queryClient.invalidateQueries({ queryKey: ['planned-activities'] }),
      queryClient.invalidateQueries({ queryKey: ['custom-activities'] }),
      queryClient.invalidateQueries({ queryKey: ['weekly-outlook'] }),
      queryClient.invalidateQueries({ queryKey: ['athlete-progression'] }),
      queryClient.invalidateQueries({ queryKey: ['data-extract-status'] }),
    ]);
  };
  const dashboardReloadMutation = useMutation({
    mutationFn: async () => {
      if (!session?.token) throw new Error('Missing auth token');
      return runComprehensiveExtract({
        token: session.token,
        owner: profile?.owner,
        payload: {
          start_day: startDayFromPreset(1),
          incremental_only: true,
          include_details: true,
          include_wellness: true,
          verify_raw_integrity: false,
        },
      });
    },
    onMutate: () => {
      setDashboardReloadResult(null);
      setDashboardReloadQueued(false);
      setDashboardReloadSawRunning(false);
    },
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ['data-extract-status'] });
      if (response.summary === 'No missing dates to fetch.') {
        setDashboardReloadResult('Dashboard already up to date.');
        await refreshDashboardViews();
        return;
      }
      setDashboardReloadResult('Background reload started.');
      setDashboardReloadQueued(true);
      setDashboardReloadSawRunning(false);
    },
    onError: (error) => {
      setDashboardReloadResult(error instanceof Error ? error.message : 'Unable to start reload.');
    },
  });
  const patchDashboardCaches = (
    updater: (payload: DashboardResponse) => DashboardResponse,
  ) => {
    queryClient.setQueriesData<DashboardResponse>(
      { queryKey: ['dashboard', profile?.owner] },
      (current) => (current ? updater(current) : current),
    );
  };
  const removeCustomActivityLocally = (dayUtc: string, lineNo: number) => {
    patchDashboardCaches((payload) => ({
      ...payload,
      weeks: payload.weeks.map((week) => ({
        ...week,
        days: week.days.map((day) =>
          day.day_utc === dayUtc
            ? {
                ...day,
                actual_activities: day.actual_activities.filter(
                  (activity) => !(activity.is_custom && activity.day_utc === dayUtc && activity.line_no === lineNo),
                ),
              }
            : day,
        ),
      })),
    }));
  };
  const insertCustomActivityLocally = (
    dayUtc: string,
    activity: DashboardActivityCard,
    slotIndex: number,
  ) => {
    patchDashboardCaches((payload) => ({
      ...payload,
      weeks: payload.weeks.map((week) => ({
        ...week,
        days: week.days.map((day) => {
          if (day.day_utc !== dayUtc) return day;
          const nextActivities = [...day.actual_activities];
          const existingIndex = nextActivities.findIndex(
            (current) =>
              current.activity_id === activity.activity_id
              || (
                current.is_custom
                && current.day_utc === activity.day_utc
                && current.line_no === activity.line_no
              ),
          );
          if (existingIndex >= 0) {
            nextActivities.splice(existingIndex, 1);
          }
          const insertionIndex = Math.max(0, Math.min(slotIndex, nextActivities.length));
          nextActivities.splice(insertionIndex, 0, activity);
          return {
            ...day,
            actual_activities: nextActivities,
          };
        }),
      })),
    }));
  };
  const removePlannedActivityLocally = (dayUtc: string, lineNo: number) => {
    patchDashboardCaches((payload) => ({
      ...payload,
      weeks: payload.weeks.map((week) => ({
        ...week,
        days: week.days.map((day) =>
          day.day_utc === dayUtc
            ? {
                ...day,
                planned_activities: day.planned_activities.filter(
                  (activity) => !(activity.day_utc === dayUtc && activity.line_no === lineNo),
                ),
              }
            : day,
        ),
      })),
    }));
  };
  const markPlannedDoneLocally = (dayUtc: string, lineNo: number) => {
    removePlannedActivityLocally(dayUtc, lineNo);
  };
  const showUndo = ({
    label,
    action,
    dayUtc,
    lineNo,
    slotIndex,
    lane,
    finalize = null,
  }: {
    label: string;
    action: () => Promise<void>;
    dayUtc?: string;
    lineNo?: number;
    slotIndex?: number;
    lane: 'planned' | 'actual';
    finalize?: (() => Promise<void>) | null;
  }) => {
    if (undoStateRef.current?.finalize) {
      void undoStateRef.current.finalize();
    }
    if (undoTimerRef.current) {
      window.clearTimeout(undoTimerRef.current);
    }
    if (undoDismissTimerRef.current) {
      window.clearTimeout(undoDismissTimerRef.current);
    }
    const id = Date.now();
    const nextUndoState = { id, lane, dayUtc, lineNo, slotIndex, label, action, finalize };
    undoStateRef.current = nextUndoState;
    setUndoState(nextUndoState);
    window.requestAnimationFrame(() => setUndoVisible(true));
    undoTimerRef.current = window.setTimeout(() => {
      if (undoStateRef.current?.id !== id) {
        undoTimerRef.current = null;
        return;
      }
      setUndoVisible(false);
      undoDismissTimerRef.current = window.setTimeout(() => {
        const pending = undoStateRef.current;
        if (!pending || pending.id !== id) {
          undoDismissTimerRef.current = null;
          return;
        }
        undoStateRef.current = null;
        if (pending.finalize) {
          void pending.finalize();
        }
        setUndoState((current) => (current?.id === id ? null : current));
        undoDismissTimerRef.current = null;
      }, 220);
      undoTimerRef.current = null;
    }, 9000);
  };
  useEffect(() => () => {
    if (undoTimerRef.current) {
      window.clearTimeout(undoTimerRef.current);
    }
    if (undoDismissTimerRef.current) {
      window.clearTimeout(undoDismissTimerRef.current);
    }
  }, []);
  useEffect(() => {
    undoStateRef.current = undoState;
  }, [undoState]);
  useEffect(() => {
    const progress = extractStatusQuery.data?.extract_progress;
    if (!dashboardReloadQueued || !progress) return;
    if (progress.running) {
      if (!dashboardReloadSawRunning) {
        setDashboardReloadSawRunning(true);
      }
      return;
    }
    if (!dashboardReloadSawRunning) return;
    setDashboardReloadQueued(false);
    setDashboardReloadSawRunning(false);
    setDashboardReloadResult('Dashboard reloaded.');
    void refreshDashboardViews();
  }, [
    dashboardReloadQueued,
    dashboardReloadSawRunning,
    extractStatusQuery.data?.extract_progress,
  ]);
  const handleUndo = async () => {
    const pending = undoState;
    if (!pending) return;
    if (undoTimerRef.current) {
      window.clearTimeout(undoTimerRef.current);
      undoTimerRef.current = null;
    }
    if (undoDismissTimerRef.current) {
      window.clearTimeout(undoDismissTimerRef.current);
      undoDismissTimerRef.current = null;
    }
    undoStateRef.current = null;
    setUndoVisible(false);
    window.setTimeout(() => setUndoState(null), 180);
    await pending.action?.();
  };
  const plannedDoneMutation = useMutation({
    mutationFn: async ({ dayUtc, lineNo }: { dayUtc: string; lineNo: number }) => {
      if (!session?.token) throw new Error('Missing auth token');
      await setPlannedManualDone({
        token: session.token,
        owner: profile?.owner,
        dayUtc,
        lineNo,
        manualDone: true,
      });
    },
    onSuccess: async () => {
      await refreshDashboardViews();
      setAddActivityDayUtc(null);
      setAddActivityText('');
      setAddActivityMode('planned');
    },
  });
  const plannedDeleteMutation = useMutation({
    mutationFn: async ({ dayUtc, lineNo }: { dayUtc: string; lineNo: number }) => {
      if (!session?.token) throw new Error('Missing auth token');
      await deletePlannedActivity({
        token: session.token,
        owner: profile?.owner,
        dayUtc,
        lineNo,
      });
    },
    onSuccess: async () => {
      await refreshDashboardViews();
    },
  });
  const plannedCreateMutation = useMutation({
    mutationFn: async ({
      dayUtc,
      workoutText,
      mode,
    }: {
      dayUtc: string;
      workoutText: string;
      mode: 'planned' | 'custom';
    }) => {
      if (!session?.token) throw new Error('Missing auth token');
      const normalizedWorkoutText = applyComposerActivityFallback(workoutText, addGeneratedActivityType);
      if (mode === 'custom') {
        return ingestCustomActivities({
          token: session.token,
          owner: profile?.owner,
          entryText: `${dayUtc}: ${normalizedWorkoutText}`,
        });
      }
      return ingestPlannedActivities({
        token: session.token,
        owner: profile?.owner,
        entryText: `${dayUtc}: ${normalizedWorkoutText}`,
      });
    },
    onSuccess: async (response, variables) => {
      if (response.errors.length > 0 && response.saved_count <= 0) {
        setAddActivityResult(response.errors[0] ?? `Unable to save ${variables.mode} activity.`);
        return;
      }
      await refreshDashboardViews();
      setAddActivityResult(null);
      setAddActivityDayUtc(null);
      setAddActivityText('');
      setAddActivityMode('planned');
    },
    onError: (error) => {
      setAddActivityResult(error instanceof Error ? error.message : 'Unable to save activity.');
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
      await refreshDashboardViews();
    },
  });
  const toggleActivityInvalidMutation = useMutation({
    mutationFn: async ({ activityId, isInvalid }: { activityId: string; isInvalid: boolean }) => {
      if (!session?.token) throw new Error('Missing auth token');
      return toggleActivityInvalid({
        token: session.token,
        owner: profile?.owner,
        activityId,
        isInvalid,
      });
    },
    onSuccess: async () => {
      await refreshDashboardViews();
    },
  });
  const generateActivityMutation = useMutation({
    mutationFn: async ({
      dayUtc,
      mode,
      activityType,
      previousActivityText,
    }: {
      dayUtc: string;
      mode: 'planned' | 'custom';
      activityType: 'running' | 'elliptical' | 'bike';
      previousActivityText?: string;
    }) => {
      if (!session?.token) throw new Error('Missing auth token');
      return generateActivitySuggestion({
        token: session.token,
        owner: profile?.owner,
        dayUtc,
        mode,
        activityType,
        previousActivityText,
      });
    },
    onSuccess: (response) => {
      setAddActivityText(response.activity_text);
      setLastGeneratedActivityText(response.activity_text);
      setAddActivityResult(null);
    },
    onError: (error) => {
      setAddActivityResult(error instanceof Error ? error.message : 'Unable to generate activity.');
    },
  });
  const displayWeeks = useMemo(() => {
    if (!query.data?.weeks) return [];
    const now = new Date();
    return query.data.weeks.map((week) => ({
      ...week,
      days: week.days.map((day) => ({
        ...day,
        planned_activities: day.planned_activities.filter((activity) =>
          plannedCardIsVisible(day.day_utc, activity.workout_text, now),
        ),
      })),
    }));
  }, [query.data?.weeks]);

  const sortedWeeks = useMemo(() => {
    if (displayWeeks.length === 0) return [];
    return [...displayWeeks].sort((a, b) => {
      const aTs = Date.parse(a.week_start);
      const bTs = Date.parse(b.week_start);
      if (Number.isNaN(aTs) && Number.isNaN(bTs)) return 0;
      if (Number.isNaN(aTs)) return 1;
      if (Number.isNaN(bTs)) return -1;
      return bTs - aTs;
    });
  }, [displayWeeks]);

  const dashboardRows = useMemo(() => {
    if (sortedWeeks.length === 0) return [];

    const rows: Array<
      | { type: 'week'; week: (typeof sortedWeeks)[number] }
      | { type: 'gap'; key: string; gapWeeks: number }
    > = [];

    for (let index = 0; index < sortedWeeks.length; index += 1) {
      const week = sortedWeeks[index];
      rows.push({ type: 'week', week });

      const nextWeek = sortedWeeks[index + 1];
      if (!nextWeek) continue;

      const currentTs = Date.parse(`${week.week_start}T00:00:00`);
      const nextTs = Date.parse(`${nextWeek.week_start}T00:00:00`);
      if (Number.isNaN(currentTs) || Number.isNaN(nextTs)) continue;

      const diffDays = Math.round((currentTs - nextTs) / (1000 * 60 * 60 * 24));
      const gapWeeks = Math.max(0, Math.round(diffDays / 7) - 1);
      if (gapWeeks > 0) {
        rows.push({
          type: 'gap',
          key: `${week.week_start}-${nextWeek.week_start}`,
          gapWeeks,
        });
      }
    }

    return rows;
  }, [sortedWeeks]);

  const totalYearWindows = useMemo(() => {
    const weeksTotal = Math.max(Number(query.data?.weeks_total ?? 0), 0);
    return Math.max(1, Math.ceil(weeksTotal / dashboardYearWindowWeeks));
  }, [dashboardYearWindowWeeks, query.data?.weeks_total, sortedWeeks.length]);

  const currentWeekStart = useMemo(() => {
    if (sortedWeeks.length === 0) return '';

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const current = sortedWeeks.find((week) => {
      const start = new Date(`${week.week_start}T00:00:00`);
      const end = new Date(`${week.week_end}T00:00:00`);
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return false;
      start.setHours(0, 0, 0, 0);
      end.setHours(0, 0, 0, 0);
      return today >= start && today <= end;
    });
    if (current) return current.week_start;

    const pastOrCurrent = sortedWeeks
      .map((week) => ({ weekStart: week.week_start, ts: Date.parse(week.week_start) }))
      .filter((item) => !Number.isNaN(item.ts) && item.ts <= today.getTime())
      .sort((a, b) => b.ts - a.ts);
    if (pastOrCurrent.length > 0) return pastOrCurrent[0].weekStart;

    return sortedWeeks[0]?.week_start ?? '';
  }, [sortedWeeks]);

  useEffect(() => {
    if (!currentWeekStart) return;
    if (lastAnchoredWeekRef.current === currentWeekStart) return;
    const node = weekRefs.current[currentWeekStart];
    if (!node) return;
    node.scrollIntoView({ block: 'start', behavior: 'auto' });
    lastAnchoredWeekRef.current = currentWeekStart;
  }, [currentWeekStart]);

  useEffect(() => {
    if (!session?.token) return;
    if (!query.data?.has_more_weeks) return;
    const nextWeeks = Math.min(visibleWeeks + dashboardPageSize, dashboardMaxWeeks);
    if (nextWeeks <= visibleWeeks) return;

    void queryClient.prefetchQuery({
      queryKey: ['dashboard', profile?.owner, nextWeeks, weekOffset, 'all'],
      queryFn: async () =>
        getDashboard({
          token: session.token,
          owner: profile?.owner,
          weeks: nextWeeks,
          weekOffset,
        }),
      staleTime: 0,
    });
  }, [dashboardMaxWeeks, dashboardPageSize, profile?.owner, query.data?.has_more_weeks, session?.token, visibleWeeks, weekOffset]);

  useEffect(() => {
    lastAnchoredWeekRef.current = '';
    setVisibleWeeks(dashboardPageSize);
  }, [dashboardPageSize, weekOffset]);

  useEffect(() => {
    const node = loadMoreRef.current;
    if (!node) return;
    if (!query.data?.has_more_weeks) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (!entry?.isIntersecting) return;
        if (query.isFetching) return;
        const nextWeeks = Math.min(visibleWeeks + dashboardPageSize, dashboardMaxWeeks);
        if (nextWeeks <= visibleWeeks) return;
        startTransition(() => {
          setVisibleWeeks(nextWeeks);
        });
      },
      { rootMargin: '900px 0px' },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [dashboardMaxWeeks, dashboardPageSize, query.data?.has_more_weeks, query.isFetching, visibleWeeks]);
  const extractRunning = Boolean(extractStatusQuery.data?.extract_progress?.running);
  const reloadButtonBusy = dashboardReloadMutation.isPending || extractRunning || dashboardReloadQueued;

  return (
    <section className="space-y-6">
      <QueryShell isLoading={query.isLoading} isError={query.isError} error={query.error} errorTitle="Unable to load dashboard">
      {query.data ? (
        <>
          {query.data.weeks.length === 0 ? (
            <div className="rounded-xl border border-border/70 bg-card/40 p-8 text-sm text-muted-foreground">
              No dashboard weeks available.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex justify-end">
                <div className="flex w-full flex-wrap items-center justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-10 w-10 border-white/10 bg-black/20 px-0 text-slate-100"
                    onClick={() => dashboardReloadMutation.mutate()}
                    disabled={!session?.token || reloadButtonBusy}
                    aria-label={reloadButtonBusy ? 'Reloading dashboard data' : 'Reload dashboard data'}
                    title={reloadButtonBusy ? 'Reloading dashboard data' : 'Reload dashboard data'}
                  >
                    {reloadButtonBusy ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <RefreshCw className="h-4 w-4" />
                    )}
                  </Button>
                  {totalYearWindows > 1 ? (
                    <div className="w-full max-w-[220px] sm:w-auto">
                      <Select value={selectedYearWindow} onValueChange={setSelectedYearWindow}>
                        <SelectTrigger className="w-full max-w-[220px]">
                          <SelectValue placeholder="Select year window" />
                        </SelectTrigger>
                        <SelectContent>
                          {Array.from({ length: totalYearWindows }).map((_, index) => (
                            <SelectItem key={index} value={String(index)}>
                              {index === 0 ? 'Latest year' : `${index}-${index + 1} years ago`}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  ) : null}
                </div>
              </div>
              {dashboardReloadResult ? (
                <p className="text-right text-xs text-slate-300/72">{dashboardReloadResult}</p>
              ) : null}
              {dashboardRows.map((row) =>
                row.type === 'gap' ? (
                  <div
                    key={row.key}
                    className="flex items-center gap-3 py-1.5"
                    aria-label={`${row.gapWeeks} week gap`}
                  >
                    <div className="h-px flex-1 bg-gradient-to-r from-transparent via-white/10 to-white/10" />
                    <div className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[11px] font-semibold text-slate-300/72">
                      <span className="tracking-[0.18em] text-slate-400/72">(...)</span>
                      <span className="ml-2">{row.gapWeeks}w gap</span>
                    </div>
                    <div className="h-px flex-1 bg-gradient-to-l from-transparent via-white/10 to-white/10" />
                  </div>
                ) : (
                  <div
                    key={row.week.week_start}
                    className="scroll-mt-24 sm:scroll-mt-28"
                    style={{ contentVisibility: 'auto', containIntrinsicSize: '720px' }}
                    ref={(node) => {
                      weekRefs.current[row.week.week_start] = node;
                    }}
                  >
                    <DashboardWeekCard
                      week={row.week}
                      onAddPlannedActivity={(dayUtc) => {
                        setAddActivityDayUtc(dayUtc);
                        setAddActivityText('');
                        setAddActivityMode(dayUtc < composerCurrentWeekStart ? 'custom' : 'planned');
                        setAddActivityResult(null);
                      }}
                      onMarkPlannedDone={(activity, index) =>
                        (() => {
                          markPlannedDoneLocally(activity.day_utc, activity.line_no);
                          showUndo({
                            lane: 'planned',
                            dayUtc: activity.day_utc,
                            lineNo: activity.line_no,
                            slotIndex: index,
                            label: 'Marked',
                            action: async () => {
                              if (!session?.token) throw new Error('Missing auth token');
                              await setPlannedManualDone({
                                token: session.token,
                                owner: profile?.owner,
                                dayUtc: activity.day_utc,
                                lineNo: activity.line_no,
                                manualDone: false,
                              });
                              await refreshDashboardViews();
                            },
                          });
                          plannedDoneMutation.mutate({ dayUtc: activity.day_utc, lineNo: activity.line_no }, { onError: () => void refreshDashboardViews() });
                        })()
                      }
                      onDeletePlannedActivity={(activity, index) =>
                        (() => {
                          removePlannedActivityLocally(activity.day_utc, activity.line_no);
                          showUndo({
                            lane: 'planned',
                            dayUtc: activity.day_utc,
                            lineNo: activity.line_no,
                            slotIndex: index,
                            label: 'Deleted',
                            action: async () => {
                              await refreshDashboardViews();
                            },
                            finalize: async () => {
                              if (!session?.token) throw new Error('Missing auth token');
                              await plannedDeleteMutation.mutateAsync(
                                { dayUtc: activity.day_utc, lineNo: activity.line_no },
                                { onError: () => void refreshDashboardViews() },
                              );
                            },
                          });
                        })()
                      }
                      onDeleteCustomActivity={(activity, index) =>
                        typeof activity.day_utc === 'string' && typeof activity.line_no === 'number'
                          ? (() => {
                              const dayUtc = activity.day_utc;
                              const lineNo = activity.line_no;
                              const activityText = String(activity.activity_text ?? '').trim();
                              removeCustomActivityLocally(dayUtc, lineNo);
                              showUndo({
                                lane: 'actual',
                                dayUtc,
                                lineNo,
                                slotIndex: index,
                                label: 'Deleted',
                                action: async () => {
                                  insertCustomActivityLocally(dayUtc, activity, index);
                                  await refreshDashboardViews();
                                },
                                finalize: async () => {
                                  if (!session?.token) throw new Error('Missing auth token');
                                  await customDeleteMutation.mutateAsync(
                                    { dayUtc, lineNo },
                                    { onError: () => void refreshDashboardViews() },
                                  );
                                },
                              });
                            })()
                          : undefined
                      }
                      onToggleActivityInvalid={(activity, nextInvalid) => {
                        if (activity.is_custom) return;
                        toggleActivityInvalidMutation.mutate(
                          { activityId: activity.activity_id, isInvalid: nextInvalid },
                          { onError: () => void refreshDashboardViews() },
                        );
                      }}
                      onSelectActivity={(activityId) => setSelectedActivityId(activityId)}
                      addingPlannedActivity={plannedCreateMutation.isPending}
                      markingPlannedDone={plannedDoneMutation.isPending}
                      deletingPlannedActivity={plannedDeleteMutation.isPending}
                      deletingCustomActivity={customDeleteMutation.isPending}
                      togglingActivityInvalid={toggleActivityInvalidMutation.isPending}
                      userTimeZone={userTimeZone}
                      undoActivity={
                        undoState?.dayUtc && typeof undoState.lineNo === 'number' && typeof undoState.slotIndex === 'number'
                          ? {
                              lane: undoState.lane,
                              dayUtc: undoState.dayUtc,
                              lineNo: undoState.lineNo,
                              slotIndex: undoState.slotIndex,
                              label: undoState.label,
                            }
                          : null
                      }
                      undoVisible={undoVisible}
                      onUndoActivity={() => void handleUndo()}
                    />
                  </div>
                ),
              )}
              {query.data.has_more_weeks ? <div ref={loadMoreRef} className="h-8 w-full" aria-hidden="true" /> : null}
            </div>
          )}
        </>
      ) : null}
      </QueryShell>
      {selectedActivityId ? (
        <Suspense fallback={null}>
          <ActivitySplitsDrawer
            activityId={selectedActivityId}
            open
            onClose={() => setSelectedActivityId(null)}
            userTimeZone={userTimeZone}
          />
        </Suspense>
      ) : null}
      {addActivityDayUtc ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-black/55 backdrop-blur-[2px]"
            aria-label="Close activity composer"
            onClick={() => {
              if (plannedCreateMutation.isPending) return;
              setAddActivityDayUtc(null);
              setAddActivityText('');
              setAddActivityMode('planned');
              setAddGeneratedActivityType('running');
              setLastGeneratedActivityText('');
              setAddActivityResult(null);
            }}
          />
          <div className="relative z-10 w-full max-w-xl rounded-2xl border border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.08),transparent_38%),linear-gradient(180deg,rgba(15,23,42,0.96),rgba(2,6,23,0.98))] p-5 shadow-[0_24px_80px_rgba(0,0,0,0.45)]">
            <div className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-200/80">Add Activity</p>
              <h3 className="text-lg font-semibold text-foreground">{formatLongDate(addActivityDayUtc)}</h3>
            </div>

            <div className="mt-4 space-y-3">
              <div className="inline-flex rounded-xl border border-white/10 bg-black/20 p-1">
                <button
                  type="button"
                  className={`rounded-lg px-3 py-1.5 text-sm transition ${
                    addActivityMode === 'planned'
                      ? 'bg-white/10 text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                  onClick={() => {
                    setAddActivityMode('planned');
                    setAddActivityResult(null);
                  }}
                  disabled={plannedCreateMutation.isPending || !canAddPlannedForComposer}
                >
                  Planned
                </button>
                <button
                  type="button"
                  className={`rounded-lg px-3 py-1.5 text-sm transition ${
                    addActivityMode === 'custom'
                      ? 'bg-white/10 text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                  onClick={() => {
                    setAddActivityMode('custom');
                    setAddActivityResult(null);
                  }}
                  disabled={plannedCreateMutation.isPending || !canAddCustomForComposer}
                >
                  Custom
                </button>
              </div>
              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                <div className="space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300/82">Generate From</p>
                  <div className="inline-flex rounded-xl border border-white/10 bg-black/20 p-1">
                    {[
                      { value: 'running', label: 'Run' },
                      { value: 'bike', label: 'Bike' },
                      { value: 'elliptical', label: 'X-train' },
                    ].map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        className={`rounded-lg px-3 py-1.5 text-sm transition ${
                          addGeneratedActivityType === option.value
                            ? 'bg-white/10 text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
                            : 'text-muted-foreground hover:text-foreground'
                        }`}
                        onClick={() => setAddGeneratedActivityType(option.value as 'running' | 'elliptical' | 'bike')}
                        disabled={plannedCreateMutation.isPending || generateActivityMutation.isPending}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                </div>
                <Button
                  variant="outline"
                  className="h-9 border-white/10 bg-black/20"
                  onClick={() => {
                    if (!addActivityDayUtc) return;
                    generateActivityMutation.mutate({
                      dayUtc: addActivityDayUtc,
                      mode: addActivityMode,
                      activityType: addGeneratedActivityType,
                      previousActivityText: lastGeneratedActivityText || addActivityText.trim(),
                    });
                  }}
                  disabled={plannedCreateMutation.isPending || generateActivityMutation.isPending}
                >
                  {generateActivityMutation.isPending ? 'Generating…' : 'Generate'}
                </Button>
              </div>
              <textarea
                className="min-h-[88px] w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2.5 text-sm text-foreground outline-none transition focus-visible:ring-2 focus-visible:ring-ring"
                value={addActivityText}
                onChange={(event) => {
                  if (addActivityResult) setAddActivityResult(null);
                  setAddActivityText(event.target.value);
                }}
                placeholder={addActivityMode === 'planned' ? 'Type the planned workout…' : 'Type the custom activity…'}
              />
              {addActivityResult ? (
                <p className="text-sm text-red-400">
                  {addActivityResult}
                </p>
              ) : null}
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-muted-foreground">
                  This will be saved directly to the selected day as a {addActivityMode} activity.
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setAddActivityDayUtc(null);
                      setAddActivityText('');
                      setAddActivityMode('planned');
                      setAddGeneratedActivityType('running');
                      setLastGeneratedActivityText('');
                      setAddActivityResult(null);
                    }}
                    disabled={plannedCreateMutation.isPending || generateActivityMutation.isPending}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={() => {
                      const workoutText = addActivityText.trim();
                      if (!workoutText || !addActivityDayUtc) return;
                      plannedCreateMutation.mutate({ dayUtc: addActivityDayUtc, workoutText, mode: addActivityMode });
                    }}
                    disabled={plannedCreateMutation.isPending || generateActivityMutation.isPending || !addActivityText.trim()}
                  >
                    {plannedCreateMutation.isPending ? 'Saving...' : 'Save'}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
