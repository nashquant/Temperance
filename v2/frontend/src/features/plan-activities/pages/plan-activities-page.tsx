import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { CalendarDays } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  SecondaryStatCard,
  secondaryPageActionButtonClassName,
  secondaryPageMutedInsetClassName,
  secondaryPageSurfaceClassName,
  secondaryPageTextAreaClassName,
} from '@/components/ui/secondary-page';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { getActivityDetail } from '@/features/dashboard/services/activity-detail-api';
import { getDashboard } from '@/features/dashboard/services/dashboard-api';
import type { ActivityDetailResponse } from '@/features/dashboard/types/activity-detail';
import type { DashboardActivityCard } from '@/features/dashboard/types/dashboard';
import { PlannedWeekChart } from '@/features/plan-activities/components/planned-week-chart';
import { PlannedWeekSelector } from '@/features/plan-activities/components/planned-week-selector';
import { usePlanActivitiesQuery } from '@/features/plan-activities/hooks/use-plan-activities-query';
import {
  deletePlannedActivity,
  ingestPlannedActivities,
  setPlannedManualDone,
  updatePlannedWorkout,
} from '@/features/plan-activities/services/plan-activities-api';
import type { PlannedActivityRow, PlannedMetricView } from '@/features/plan-activities/types/plan-activities';
import { queryClient } from '@/lib/query-client';

function dayLabel(isoDay: string): string {
  return new Intl.DateTimeFormat('en-US', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }).format(
    new Date(`${isoDay}T00:00:00Z`),
  );
}

function compactDayLabel(isoDay: string): string {
  return new Intl.DateTimeFormat('en-US', { weekday: 'short', day: 'numeric', timeZone: 'UTC' }).format(
    new Date(`${isoDay}T00:00:00Z`),
  );
}

function addDaysToIsoDay(isoDay: string, days: number): string {
  const [year, month, day] = isoDay.split('-').map((value) => Number(value));
  const date = new Date(Date.UTC(year, month - 1, day));
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function defaultPlannedActivityDay(weekStart?: string): string {
  if (!weekStart) return new Date().toISOString().slice(0, 10);
  const weekEnd = addDaysToIsoDay(weekStart, 6);
  const today = new Date().toISOString().slice(0, 10);
  if (today >= weekStart && today <= weekEnd) return today;
  return weekStart;
}

type QuickAddActivityType = 'run' | 'xtrain';

const QUICK_ADD_ACTIVITY_OPTIONS: Array<{ value: QuickAddActivityType; label: string; token: string }> = [
  { value: 'run', label: 'Run', token: 'run' },
  { value: 'xtrain', label: 'X-Train', token: 'xtrain' },
];

function workoutTextHasExplicitActivity(text: string): boolean {
  const normalized = String(text || '').toLowerCase();
  return /(treadmill|run|ellipt|xtrain|x-train|cross train|cross-train|cycl|bike)/.test(normalized);
}

function buildQuickAddWorkoutText(workoutText: string, activityType: QuickAddActivityType): string {
  const normalizedWorkout = String(workoutText || '').trim();
  if (!normalizedWorkout) return '';
  if (workoutTextHasExplicitActivity(normalizedWorkout)) return normalizedWorkout;
  const prefix = QUICK_ADD_ACTIVITY_OPTIONS.find((option) => option.value === activityType)?.token ?? 'run';
  return `${prefix} ${normalizedWorkout}`.trim();
}

function splitWorkoutDateOverride(text: string): { dateText: string | null; workoutText: string } {
  const raw = String(text || '').trim();
  const match = raw.match(
    /^\s*((?:today|tomorrow|yesterday|t(?:[+-]\d+)?|\d{4}-\d{2}-\d{2}|\d{1,2}\/\d{1,2}\/\d{4}|\d{1,2}[A-Za-z]{3}\d{2}))\s*:\s*(.+)$/i,
  );
  if (!match) return { dateText: null, workoutText: raw };
  return {
    dateText: String(match[1] || '').trim(),
    workoutText: String(match[2] || '').trim(),
  };
}

function buildQuickAddEntryText(
  quickAddDay: string,
  quickAddWorkout: string,
  quickAddActivityType: QuickAddActivityType,
): string {
  const { dateText, workoutText } = splitWorkoutDateOverride(quickAddWorkout);
  const resolvedDateText = dateText || quickAddDay;
  const resolvedWorkoutText = buildQuickAddWorkoutText(workoutText, quickAddActivityType);
  return `${resolvedDateText}: ${resolvedWorkoutText}`.trim();
}

function clipboardSportToken(rawSport: string): string {
  const normalized = String(rawSport || '').trim().toLowerCase();
  if (!normalized) return 'activity';
  if (normalized.includes('treadmill')) return 'treadmill';
  if (normalized.includes('run')) return 'run';
  if (normalized.includes('ellipt')) return 'elliptical';
  if (normalized.includes('cycl') || normalized.includes('bike')) return 'bike';
  if (normalized.includes('swim')) return 'swim';
  if (normalized.includes('strength') || normalized.includes('lift')) return 'strength';
  return normalized.replace(/[_-]+/g, ' ').split(/\s+/)[0] || 'activity';
}

function parseClipboardDurationLabelSeconds(label: string): number {
  const raw = String(label || '').trim().toLowerCase();
  if (!raw) return 0;
  const quotedMatch = raw.match(/^(?:(\d+)\s*h\s*)?(?:(\d+)\s*')?\s*(?:(\d+)\s*")?$/);
  if (quotedMatch) {
    const hours = Number(quotedMatch[1] || 0);
    const minutes = Number(quotedMatch[2] || 0);
    const seconds = Number(quotedMatch[3] || 0);
    return hours * 3600 + minutes * 60 + seconds;
  }
  const colonMatch = raw.match(/^(?:(\d+):)?(\d{1,2}):(\d{2})$/);
  if (colonMatch) {
    const hours = Number(colonMatch[1] || 0);
    const minutes = Number(colonMatch[2] || 0);
    const seconds = Number(colonMatch[3] || 0);
    return hours * 3600 + minutes * 60 + seconds;
  }
  const hourMatch = raw.match(/(\d+)\s*h/);
  const minuteMatch = raw.match(/(\d+)\s*m/);
  const secondMatch = raw.match(/(\d+)\s*s/);
  const hours = Number(hourMatch?.[1] || 0);
  const minutes = Number(minuteMatch?.[1] || 0);
  const seconds = Number(secondMatch?.[1] || 0);
  return hours * 3600 + minutes * 60 + seconds;
}

function formatRoundedClipboardDuration(durationSeconds: number): { label: string; roundedSeconds: number } {
  const totalSeconds = Math.max(0, Math.round(Number(durationSeconds) || 0));
  if (totalSeconds < 60) {
    return { label: `0'${String(totalSeconds).padStart(2, '0')}"`, roundedSeconds: totalSeconds };
  }

  const nearestMinute = Math.round(totalSeconds / 60) * 60;
  const nearestHalfMinute = Math.round(totalSeconds / 30) * 30;
  const candidates = [nearestMinute, nearestHalfMinute]
    .filter((candidate) => candidate > 0)
    .sort((left, right) => {
      const leftError = Math.abs(left - totalSeconds);
      const rightError = Math.abs(right - totalSeconds);
      if (leftError !== rightError) return leftError - rightError;
      return (left % 60 === 0 ? -1 : 1) - (right % 60 === 0 ? -1 : 1);
    });

  const rounded = candidates.find((candidate) => Math.abs(candidate - totalSeconds) / totalSeconds <= 0.005) ?? totalSeconds;
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  const seconds = rounded % 60;

  if (hours > 0) {
    if (seconds === 0) return { label: `${hours}h${String(minutes).padStart(2, '0')}'`, roundedSeconds: rounded };
    return { label: `${hours}h${String(minutes).padStart(2, '0')}'${String(seconds).padStart(2, '0')}"`, roundedSeconds: rounded };
  }
  if (seconds === 0) return { label: `${minutes}'`, roundedSeconds: rounded };
  return { label: `${minutes}'${String(seconds).padStart(2, '0')}"`, roundedSeconds: rounded };
}

function parseClipboardIntensity(label: string): { kind: 'pace' | 'hr' | 'other'; value: number; text: string } {
  const raw = String(label || '').trim();
  if (!raw) return { kind: 'other', value: 0, text: '' };
  const hrMatch = raw.match(/^(\d+)\s*bpm$/i);
  if (hrMatch) {
    return { kind: 'hr', value: Number(hrMatch[1] || 0), text: `${Math.round(Number(hrMatch[1] || 0))}bpm` };
  }
  const paceMatch = raw.match(/^(\d+):(\d{2})\/km$/i);
  if (paceMatch) {
    const minutes = Number(paceMatch[1] || 0);
    const seconds = Number(paceMatch[2] || 0);
    return { kind: 'pace', value: minutes * 60 + seconds, text: `${minutes}:${String(seconds).padStart(2, '0')}/km` };
  }
  return { kind: 'other', value: 0, text: raw };
}

function formatClipboardIntensity(kind: 'pace' | 'hr' | 'other', value: number, fallbackText: string): string {
  if (kind === 'hr') return `${Math.round(value)}bpm`;
  if (kind === 'pace') {
    const totalSeconds = Math.max(0, Math.round(value));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${String(seconds).padStart(2, '0')}/km`;
  }
  return fallbackText;
}

type ClipboardChunk = {
  durationLabel: string;
  roundedDurationSeconds: number;
  intensityKind: 'pace' | 'hr' | 'other';
  intensityValue: number;
  intensityLabel: string;
};

function clipboardChunksCanRepeat(left: ClipboardChunk, right: ClipboardChunk): boolean {
  if (left.roundedDurationSeconds !== right.roundedDurationSeconds) return false;
  if (left.intensityKind !== right.intensityKind) return false;
  if (left.intensityKind === 'pace') return Math.abs(left.intensityValue - right.intensityValue) <= 2;
  if (left.intensityKind === 'hr') return Math.abs(left.intensityValue - right.intensityValue) <= 2;
  return left.intensityLabel === right.intensityLabel;
}

function compressClipboardChunks(chunks: ClipboardChunk[]): Array<{ count: number; durationLabel: string; intensityLabel: string }> {
  const groups: Array<{ count: number; durationLabel: string; intensityLabel: string }> = [];
  let index = 0;

  while (index < chunks.length) {
    const current = chunks[index];
    let end = index + 1;
    while (end < chunks.length && clipboardChunksCanRepeat(current, chunks[end])) {
      end += 1;
    }

    const group = chunks.slice(index, end);
    const representative = group[Math.floor(group.length / 2)] ?? current;
    const averagedIntensity =
      representative.intensityKind === 'other'
        ? representative.intensityLabel
        : formatClipboardIntensity(
            representative.intensityKind,
            group.reduce((sum, item) => sum + item.intensityValue, 0) / group.length,
            representative.intensityLabel,
          );

    groups.push({
      count: group.length,
      durationLabel: representative.durationLabel,
      intensityLabel: averagedIntensity,
    });
    index = end;
  }

  return groups;
}

function buildActualClipboardTextFromDetail(detail: ActivityDetailResponse): string {
  const rawSource = String(detail.raw?.workout_text || detail.raw?.activity_text || '').trim();
  if (rawSource) return rawSource;

  const sportToken = clipboardSportToken(String(detail.activity?.sport_type || ''));
  const runningLike = sportToken === 'run' || sportToken === 'treadmill';
  const laps = Array.isArray(detail.split_rows) ? detail.split_rows : [];
  const chunks = laps
    .map((lap, index) => {
      const durationSeconds = Number(lap.duration_seconds) || parseClipboardDurationLabelSeconds(lap.duration_label);
      const rawDurationLabel = String(lap.duration_label || '').trim();
      const roundedDuration = durationSeconds > 0 ? formatRoundedClipboardDuration(durationSeconds) : null;
      const durationLabel = String(roundedDuration?.label || rawDurationLabel).trim();
      if (!durationLabel) return null;

      let intensityLabel = '';
      if (runningLike) {
        const paceLabel = String(lap.pace_label || '').trim();
        if (paceLabel && paceLabel !== '-') {
          intensityLabel = paceLabel;
        } else if (Number(lap.avg_hr) > 0) {
          intensityLabel = `${Math.round(Number(lap.avg_hr))}bpm`;
        }
      } else if (Number(lap.avg_hr) > 0) {
        intensityLabel = `${Math.round(Number(lap.avg_hr))}bpm`;
      } else {
        const paceEqvLabel = String(lap.pace_eqv_label || '').trim();
        if (paceEqvLabel && paceEqvLabel !== '-') {
          intensityLabel = paceEqvLabel;
        }
      }

      const parsedIntensity = parseClipboardIntensity(intensityLabel);
      return {
        index,
        durationLabel,
        roundedDurationSeconds: roundedDuration?.roundedSeconds ?? durationSeconds,
        intensityKind: parsedIntensity.kind,
        intensityValue: parsedIntensity.value,
        intensityLabel: parsedIntensity.text,
      };
    })
    .filter((chunk): chunk is ClipboardChunk & { index: number } => chunk !== null);

  if (chunks.length > 0) {
    return compressClipboardChunks(chunks).map((chunk, index) => {
      const head = index === 0 ? `${sportToken} ` : '';
      const body = chunk.count > 1 ? `${chunk.count}x${chunk.durationLabel}` : chunk.durationLabel;
      return `${head}${body}${chunk.intensityLabel ? ` @${chunk.intensityLabel}` : ''}`.trim();
    }).join(' + ');
  }

  const durationMinutes = Math.max(0, Math.round(Number(detail.activity?.duration_min) || 0));
  const durationLabel = durationMinutes > 0 ? `${durationMinutes}min` : 'activity';
  const paceLabel = String(detail.activity?.avg_pace_display || '').trim();
  const avgHr = Math.round(Number(detail.activity?.avg_hr) || 0);
  const intensityLabel = runningLike
    ? (paceLabel && paceLabel !== '-' ? paceLabel : avgHr > 0 ? `${avgHr}bpm` : '')
    : avgHr > 0
      ? `${avgHr}bpm`
      : '';

  return `${sportToken} ${durationLabel}${intensityLabel ? ` @${intensityLabel}` : ''}`.trim();
}

function buildActualClipboardTextFromCard(activity: DashboardActivityCard): string {
  const sportToken = clipboardSportToken(String(activity.sport || ''));
  const durationLabel = String(activity.duration_label || '').trim() || 'activity';
  const paceLabel = String(activity.pace_label || '').trim();
  const hrLabel = String(activity.hr_label || '').trim();
  const runningLike = sportToken === 'run' || sportToken === 'treadmill';
  const intensityLabel = runningLike
    ? (paceLabel && paceLabel !== '-' ? paceLabel : hrLabel && hrLabel !== '-' ? hrLabel : '')
    : hrLabel && hrLabel !== '-'
      ? hrLabel
      : paceLabel && paceLabel !== '-'
        ? paceLabel
        : '';

  return `${sportToken} ${durationLabel}${intensityLabel ? ` @${intensityLabel}` : ''}`.trim();
}

async function writeClipboardText(payload: string): Promise<void> {
  const text = String(payload || '');
  if (!text.trim()) throw new Error('Nothing to copy');

  try {
    await navigator.clipboard.writeText(text);
    return;
  } catch {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', 'true');
    textarea.style.position = 'fixed';
    textarea.style.top = '-9999px';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);

    const didCopy = document.execCommand('copy');
    document.body.removeChild(textarea);
    if (!didCopy) {
      throw new Error('Clipboard write failed');
    }
  }
}

export function PlanActivitiesPage(): JSX.Element {
  return <PlanActivitiesSection />;
}

interface PlanActivitiesSectionProps {
  embedded?: boolean;
}

export function PlanActivitiesSection({ embedded = false }: PlanActivitiesSectionProps): JSX.Element {
  const deleteUndoWindowMs = 6000;
  const { session, profile } = useAuth();
  const query = usePlanActivitiesQuery(4);
  const [metric, setMetric] = useState<PlannedMetricView>('tss');
  const [selectedWeek, setSelectedWeek] = useState<string>('');
  const [entryText, setEntryText] = useState('');
  const [quickAddDay, setQuickAddDay] = useState(() => new Date().toISOString().slice(0, 10));
  const [quickAddActivityType, setQuickAddActivityType] = useState<QuickAddActivityType>('run');
  const [quickAddWorkout, setQuickAddWorkout] = useState('');
  const [ingestResult, setIngestResult] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [rowSaveResults, setRowSaveResults] = useState<Record<string, { tone: 'error' | 'success'; message: string }>>({});
  const [pendingDelete, setPendingDelete] = useState<{ id: number; row: PlannedActivityRow } | null>(null);
  const [deleteResult, setDeleteResult] = useState<string | null>(null);
  const [copyResult, setCopyResult] = useState<string | null>(null);
  const [copyMode, setCopyMode] = useState<'planned' | 'actual' | null>(null);
  const pendingDeleteTimerRef = useRef<number | null>(null);
  const pendingDeleteRef = useRef<{ id: number; row: PlannedActivityRow } | null>(null);
  const sanitizedRows = useMemo(
    () =>
      (query.data?.rows ?? []).filter((row) => {
        const workoutText = String(row.workout_text ?? '').trim();
        const activityLabel = String(row.activity ?? '').trim();
        return workoutText.length > 0 || activityLabel.length > 0;
      }),
    [query.data?.rows],
  );

  const refetchPlan = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['plan-activities'] }),
      queryClient.invalidateQueries({ queryKey: ['weekly-outlook'] }),
    ]);
  };

  const manualDoneMutation = useMutation({
    mutationFn: async ({ dayUtc, lineNo, manualDone }: { dayUtc: string; lineNo: number; manualDone: boolean }) => {
      if (!session?.token) throw new Error('Missing auth token');
      await setPlannedManualDone({
        token: session.token,
        owner: profile?.owner,
        dayUtc,
        lineNo,
        manualDone,
      });
    },
    onSuccess: refetchPlan,
  });

  const deleteMutation = useMutation({
    mutationFn: async ({ dayUtc, lineNo }: { dayUtc: string; lineNo: number }) => {
      if (!session?.token) throw new Error('Missing auth token');
      await deletePlannedActivity({
        token: session.token,
        owner: profile?.owner,
        dayUtc,
        lineNo,
      });
    },
    onSuccess: refetchPlan,
  });

  const ingestMutation = useMutation({
    mutationFn: async ({ text }: { text: string; source: 'composer' | 'inline-row' }) => {
      if (!session?.token) throw new Error('Missing auth token');
      return ingestPlannedActivities({
        token: session.token,
        owner: profile?.owner,
        entryText: text,
      });
    },
    onSuccess: async (response, variables) => {
      await refetchPlan();
      if (response.errors.length > 0 && response.saved_count <= 0) {
        setIngestResult(response.errors[0] ?? 'Unable to save planned activities.');
      } else if (response.errors.length > 0) {
        setIngestResult(`Saved ${response.saved_count}. Some entries were skipped.`);
      } else {
        setIngestResult(`Saved ${response.saved_count} planned activit${response.saved_count === 1 ? 'y' : 'ies'}.`);
      }
      if (response.saved_count > 0) {
        if (variables.source === 'composer') {
          setEntryText('');
        } else {
          setQuickAddWorkout('');
        }
      }
    },
    onError: (error) => {
      setIngestResult(error instanceof Error ? error.message : 'Unable to save planned activities.');
    },
  });

  const workoutUpdateMutation = useMutation({
    mutationFn: async ({ dayUtc, lineNo, workoutText, manualDone }: { dayUtc: string; lineNo: number; workoutText: string; manualDone: boolean }) => {
      if (!session?.token) throw new Error('Missing auth token');
      await updatePlannedWorkout({
        token: session.token,
        owner: profile?.owner,
        dayUtc,
        lineNo,
        workoutText,
        manualDone,
      });
    },
    onSuccess: async (_response, variables) => {
      const rowKey = `${variables.dayUtc}-${variables.lineNo}`;
      setRowSaveResults((previous) => ({
        ...previous,
        [rowKey]: {
          tone: 'success',
          message: 'Saved.',
        },
      }));
      await refetchPlan();
    },
    onError: (error, variables) => {
      const rowKey = `${variables.dayUtc}-${variables.lineNo}`;
      setRowSaveResults((previous) => ({
        ...previous,
        [rowKey]: {
          tone: 'error',
          message: error instanceof Error ? error.message : 'Unable to save planned activity.',
        },
      }));
    },
  });

  const weeks = query.data?.weeks ?? [];
  const today = new Date();
  const currentWeekStartDate = new Date(today);
  const dayOffset = (currentWeekStartDate.getDay() + 6) % 7;
  currentWeekStartDate.setDate(currentWeekStartDate.getDate() - dayOffset);
  const currentWeekStart = `${currentWeekStartDate.getFullYear()}-${String(currentWeekStartDate.getMonth() + 1).padStart(2, '0')}-${String(currentWeekStartDate.getDate()).padStart(2, '0')}`;
  const defaultWeek = weeks.find((week) => week.week_start === currentWeekStart)?.week_start ?? weeks[0]?.week_start ?? '';
  const effectiveWeek = selectedWeek || defaultWeek;
  const selectedWeekMeta = weeks.find((week) => week.week_start === effectiveWeek);

  const selectedRows = useMemo(() => {
    if (!effectiveWeek) return [];
    const weekEnd = addDaysToIsoDay(effectiveWeek, 6);
    return sanitizedRows.filter((row) => {
      return row.day_utc >= effectiveWeek && row.day_utc <= weekEnd;
    });
  }, [effectiveWeek, sanitizedRows]);

  useEffect(() => {
    const next: Record<string, string> = {};
    selectedRows.forEach((row) => {
      next[`${row.day_utc}-${row.line_no}`] = row.workout_text;
    });
    setEditValues(next);
  }, [selectedRows]);

  useEffect(() => {
    setQuickAddDay(defaultPlannedActivityDay(effectiveWeek));
  }, [effectiveWeek]);

  const chartRows = useMemo(() => {
    if (!effectiveWeek) return [];
    return Array.from({ length: 7 }).map((_, index) => {
      const iso = addDaysToIsoDay(effectiveWeek, index);
      const rowValue = selectedRows
        .filter((row) => row.day_utc === iso)
        .reduce((sum, row) => sum + Number(row[metric] ?? 0), 0);
      const tssBasis = selectedRows
        .filter((row) => row.day_utc === iso)
        .reduce((sum, row) => sum + Number(row.tss ?? 0), 0);
      return {
        dayLabel: dayLabel(iso),
        value: rowValue,
        tssBasis,
      };
    });
  }, [effectiveWeek, metric, selectedRows]);

  const selectedWeekClipboardText = useMemo(() => {
    return selectedRows
      .slice()
      .sort((left, right) => {
        if (left.day_utc !== right.day_utc) return left.day_utc.localeCompare(right.day_utc);
        return left.line_no - right.line_no;
      })
      .map((row) => {
        const rowKey = `${row.day_utc}-${row.line_no}`;
        const workoutText = String(editValues[rowKey] ?? row.workout_text ?? '').trim();
        return workoutText ? `${row.day_utc}: ${workoutText}` : '';
      })
      .filter(Boolean)
      .join('\n');
  }, [editValues, selectedRows]);

  const goalItems = query.data
    ? [
        { label: 'TSS Goal', value: Math.round(query.data.goals.tss).toString() },
        { label: 'rTSS Goal', value: Math.round(query.data.goals.rtss).toString() },
        { label: 'Distance Goal', value: `${Math.round(query.data.goals.distance_eqv_km)} km` },
      ]
    : [];

  const selectedWeekItems = selectedWeekMeta
    ? [
        { label: 'Activities', value: String(selectedWeekMeta.planned_activities) },
        { label: 'Duration', value: `${selectedWeekMeta.duration_h.toFixed(1)}h` },
        { label: 'TSS', value: String(Math.round(selectedWeekMeta.tss)) },
        { label: 'rTSS', value: String(Math.round(selectedWeekMeta.rtss)) },
        { label: 'Dist Eqv', value: `${selectedWeekMeta.distance_eqv_km.toFixed(1)} km` },
      ]
    : [];

  const clearPendingDeleteTimer = () => {
    if (pendingDeleteTimerRef.current) {
      window.clearTimeout(pendingDeleteTimerRef.current);
      pendingDeleteTimerRef.current = null;
    }
  };

  const finalizePendingDelete = async (candidate: { id: number; row: PlannedActivityRow }) => {
    try {
      await deleteMutation.mutateAsync({
        dayUtc: candidate.row.day_utc,
        lineNo: candidate.row.line_no,
      });
      setDeleteResult(`Deleted ${candidate.row.activity || 'planned activity'}.`);
    } catch (error) {
      setDeleteResult(error instanceof Error ? error.message : 'Unable to delete planned activity.');
      setPendingDelete((current) => (current?.id === candidate.id ? null : current));
      pendingDeleteRef.current = null;
      return;
    }
    setPendingDelete((current) => (current?.id === candidate.id ? null : current));
    pendingDeleteRef.current = null;
  };

  const queueDelete = (row: PlannedActivityRow) => {
    clearPendingDeleteTimer();
    const existingPendingDelete = pendingDeleteRef.current;
    if (existingPendingDelete) {
      void finalizePendingDelete(existingPendingDelete);
    }
    const candidate = { id: Date.now(), row };
    pendingDeleteRef.current = candidate;
    setPendingDelete(candidate);
    setDeleteResult(null);
    pendingDeleteTimerRef.current = window.setTimeout(() => {
      if (pendingDeleteRef.current?.id !== candidate.id) return;
      void finalizePendingDelete(candidate);
    }, deleteUndoWindowMs);
  };

  const handleUndoDelete = () => {
    clearPendingDeleteTimer();
    pendingDeleteRef.current = null;
    setPendingDelete(null);
    setDeleteResult(null);
  };

  useEffect(() => () => {
    clearPendingDeleteTimer();
  }, []);

  const handleCopyWeekToClipboard = async () => {
    setCopyMode('planned');
    const payload = selectedWeekClipboardText.trim();
    if (!payload) {
      setCopyResult('No planned activities to copy for this week.');
      setCopyMode(null);
      return;
    }
    try {
      await writeClipboardText(payload);
      setCopyResult(`Copied ${selectedRows.length} planned activit${selectedRows.length === 1 ? 'y' : 'ies'} to clipboard.`);
    } catch {
      setCopyResult('Unable to copy the current week to clipboard.');
    } finally {
      setCopyMode(null);
    }
  };

  const handleCopyActualWeekToClipboard = async () => {
    if (!session?.token) {
      setCopyResult('Missing auth token.');
      return;
    }

    setCopyMode('actual');
    try {
      const cachedDashboardEntries = queryClient.getQueriesData<Awaited<ReturnType<typeof getDashboard>>>({
        queryKey: ['dashboard', profile?.owner],
      });
      const cachedDashboardPayload = cachedDashboardEntries
        .map(([, data]) => data)
        .find((data) => data?.weeks?.some((week) => week.week_start === effectiveWeek));
      const dashboardPayload =
        cachedDashboardPayload
        ?? (await queryClient.fetchQuery({
          queryKey: ['dashboard', profile?.owner, Math.max(4, weeks.length || 0), 0, 'all'],
          queryFn: () =>
            getDashboard({
              token: session.token,
              owner: profile?.owner,
              weeks: Math.max(4, weeks.length || 0),
            }),
        }));
      if (!dashboardPayload) {
        setCopyResult('Unable to load the selected week’s actual activities.');
        return;
      }

      const selectedDashboardWeek = dashboardPayload.weeks.find((week) => week.week_start === effectiveWeek);
      const actualRows = (selectedDashboardWeek?.days ?? []).flatMap((day) =>
        day.actual_activities.map((activity) => ({
          dayUtc: day.day_utc,
          activity,
        })),
      );

      if (actualRows.length === 0) {
        setCopyResult('No actual activities to copy for this week.');
        return;
      }

      const lineResults = await Promise.allSettled(
          actualRows.map(async ({ dayUtc, activity }) => {
            try {
              const detail = await queryClient.fetchQuery({
                queryKey: ['activity-detail', profile?.owner, activity.activity_id],
                queryFn: () =>
                  getActivityDetail({
                    token: session.token,
                    owner: profile?.owner,
                    activityId: activity.activity_id,
                  }),
              });
              const encoded = buildActualClipboardTextFromDetail(detail);
              return encoded ? `${dayUtc}: ${encoded}` : '';
            } catch {
              const fallback = buildActualClipboardTextFromCard(activity);
              return fallback ? `${dayUtc}: ${fallback}` : '';
            }
          }),
      );
      const lines = lineResults
        .flatMap((result) => (result.status === 'fulfilled' ? [result.value] : []))
        .filter(Boolean);

      if (lines.length === 0) {
        setCopyResult('Unable to build clipboard text for the selected week’s actual activities.');
        return;
      }

      await writeClipboardText(lines.join('\n'));
      setCopyResult(`Copied ${lines.length} actual activit${lines.length === 1 ? 'y' : 'ies'} to clipboard.`);
    } catch {
      setCopyResult('Unable to copy actual activities for the selected week.');
    } finally {
      setCopyMode(null);
    }
  };

  return (
    <section className="space-y-6">
      <div>
        {embedded ? (
          <h2 className="text-xl font-semibold tracking-tight">Plan Activities</h2>
        ) : (
          <h1 className="text-2xl font-semibold tracking-tight">Plan Activities</h1>
        )}
      </div>

      {!query.isLoading && !query.isError && query.data ? (
        <>
          <Card className={`${secondaryPageSurfaceClassName} sm:hidden`}>
            <CardContent className="grid gap-2 p-4">
              {goalItems.map((item) => (
                <div
                  key={item.label}
                  className={`flex items-center justify-between ${secondaryPageMutedInsetClassName} px-3 py-2.5`}
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">{item.label}</p>
                  <p className="text-sm font-semibold text-slate-50">{item.value}</p>
                </div>
              ))}
            </CardContent>
          </Card>
          <div className="hidden flex-wrap items-center gap-2 sm:flex">
            <Badge variant="outline">TSS goal: {Math.round(query.data.goals.tss)}</Badge>
            <Badge variant="outline">rTSS goal: {Math.round(query.data.goals.rtss)}</Badge>
            <Badge variant="outline">Distance goal: {Math.round(query.data.goals.distance_eqv_km)} km</Badge>
          </div>
        </>
      ) : null}

      <Card className={secondaryPageSurfaceClassName}>
        <CardContent className="space-y-3 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.08),transparent_38%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] p-3 sm:space-y-4 sm:p-5">
          <h2 className="text-lg font-semibold text-foreground">Add Planned Activity</h2>
          <textarea
            className={`min-h-[104px] ${secondaryPageTextAreaClassName} sm:min-h-[120px]`}
            placeholder="e.g. 3Mar26: 80min elliptical @140bpm; 2026-03-26: 10min run @4:50 + 5x6min @3:40/km"
            value={entryText}
            onChange={(event) => setEntryText(event.target.value)}
          />
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
            <p className="text-xs text-muted-foreground">Multiple entries are supported with new lines, `;`, or `,`.</p>
            <div className="flex w-full flex-col items-stretch gap-2 sm:w-auto sm:flex-row sm:items-center">
              <Button
                className={`${secondaryPageActionButtonClassName} w-full sm:w-auto`}
                onClick={() => ingestMutation.mutate({ text: entryText, source: 'composer' })}
                disabled={ingestMutation.isPending || !entryText.trim()}
              >
                {ingestMutation.isPending ? 'Saving...' : 'Save'}
              </Button>
              {ingestResult ? <p className="text-xs text-muted-foreground">{ingestResult}</p> : null}
            </div>
          </div>
        </CardContent>
      </Card>

      {query.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-56 w-full" />
        </div>
      ) : null}

      {query.isError ? (
        <Alert className="border-red-300 text-red-700 dark:border-red-900 dark:text-red-300">
          <AlertTitle>Unable to load planned activities</AlertTitle>
          <AlertDescription>{query.error instanceof Error ? query.error.message : 'Unexpected error.'}</AlertDescription>
        </Alert>
      ) : null}

      {deleteResult ? (
        <Alert className="border-white/15 bg-white/[0.03] text-slate-100">
          <AlertTitle>Delete status</AlertTitle>
          <AlertDescription>{deleteResult}</AlertDescription>
        </Alert>
      ) : null}

      {copyResult ? (
        <Alert className="border-white/15 bg-white/[0.03] text-slate-100">
          <AlertTitle>Clipboard</AlertTitle>
          <AlertDescription>{copyResult}</AlertDescription>
        </Alert>
      ) : null}

      {!query.isLoading && !query.isError && query.data ? (
        <>
          {weeks.length === 0 ? (
              <Card className={secondaryPageSurfaceClassName}>
                <CardContent className="p-8 text-sm text-slate-300/72">No planned activities found in this time window.</CardContent>
              </Card>
          ) : (
            <>
              <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-2">
                <PlannedWeekSelector weeks={weeks} value={effectiveWeek} onValueChange={(next) => setSelectedWeek(next)} />
                <Button
                  variant="outline"
                  className="border-white/10 bg-black/15"
                  onClick={() => void handleCopyWeekToClipboard()}
                  disabled={copyMode !== null || !selectedWeekClipboardText.trim()}
                >
                  {copyMode === 'planned' ? 'Copying planned…' : 'Copy Planned'}
                </Button>
                <Button
                  variant="outline"
                  className="border-white/10 bg-black/15"
                  onClick={() => void handleCopyActualWeekToClipboard()}
                  disabled={copyMode !== null || !effectiveWeek}
                >
                  {copyMode === 'actual' ? 'Copying actual…' : 'Copy Actual'}
                </Button>
              </div>

              {selectedWeekMeta ? (
                <Card className={secondaryPageSurfaceClassName}>
                  <CardContent className="p-4">
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                      {selectedWeekItems.map((item) => (
                        <SecondaryStatCard
                          key={item.label}
                          label={item.label}
                          value={item.value}
                          className="min-h-[unset]"
                        />
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ) : null}

              <PlannedWeekChart data={chartRows} metric={metric} onMetricChange={setMetric} />

              <Card className={secondaryPageSurfaceClassName}>
                <CardContent className="p-0">
                  <div className="overflow-x-auto rounded-2xl pb-1">
                    <table className="min-w-[980px] w-full table-fixed text-sm">
                      <colgroup>
                        <col className="w-[64px]" />
                        <col className="w-[74px]" />
                        <col className="w-[132px]" />
                        <col className="w-auto" />
                        <col className="w-[82px]" />
                        <col className="w-[82px]" />
                        <col className="w-[104px]" />
                        <col className="w-[74px]" />
                        <col className="w-[148px]" />
                      </colgroup>
                      <thead className="bg-white/5 text-slate-300/72">
                        <tr>
                          <th className="px-2 py-2 text-left sm:px-3">Done</th>
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
                        <tr className="border-t border-white/10 bg-white/[0.03]">
                          <td className="px-2 py-2 sm:px-3">
                            <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-dashed border-white/10 bg-white/[0.02] text-base font-semibold text-slate-200">
                              +
                            </div>
                          </td>
                          <td className="px-2 py-2 sm:px-3">
                            <label
                              className="relative flex h-9 w-9 cursor-pointer items-center justify-center rounded-xl border border-white/10 bg-black/20 text-slate-200 transition hover:bg-white/[0.05]"
                              title={`Selected day: ${dayLabel(quickAddDay)}`}
                              aria-label={`Select planned day. Current day is ${dayLabel(quickAddDay)}.`}
                            >
                              <CalendarDays className="pointer-events-none h-4 w-4" />
                              <input
                                type="date"
                                value={quickAddDay}
                                onChange={(event) => setQuickAddDay(event.target.value)}
                                className="absolute inset-0 h-full w-full cursor-pointer appearance-none opacity-0"
                                aria-hidden="true"
                                tabIndex={-1}
                              />
                            </label>
                          </td>
                          <td className="px-2 py-2 sm:px-3">
                            <div className="inline-flex rounded-xl bg-white/[0.03] p-1">
                              {QUICK_ADD_ACTIVITY_OPTIONS.map((option) => {
                                const isActive = quickAddActivityType === option.value;
                                return (
                                  <button
                                    key={option.value}
                                    type="button"
                                    className={`rounded-lg px-2.5 py-1.5 text-[11px] font-semibold leading-none whitespace-nowrap transition ${
                                      isActive
                                        ? 'bg-white/10 text-slate-50'
                                        : 'text-slate-300/62 hover:text-slate-100'
                                    }`}
                                    onClick={() => setQuickAddActivityType(option.value)}
                                  >
                                    {option.label}
                                  </button>
                                );
                              })}
                            </div>
                          </td>
                          <td className="px-2 py-2 sm:px-3">
                            <input
                              className="min-w-[260px] w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-foreground outline-none transition placeholder:text-slate-400/55 focus:border-sky-300/40 focus:ring-2 focus:ring-sky-300/20"
                              value={quickAddWorkout}
                              onChange={(event) => setQuickAddWorkout(event.target.value)}
                              placeholder="e.g. 10min @ 4:30/km + 3x10min @ 3:45/km"
                            />
                          </td>
                          <td className="px-2 py-2 text-right text-slate-300/45 sm:px-3">-</td>
                          <td className="px-2 py-2 text-right text-slate-300/45 sm:px-3">-</td>
                          <td className="px-2 py-2 text-right text-slate-300/45 sm:px-3">-</td>
                          <td className="px-2 py-2 text-right text-slate-300/45 sm:px-3">-</td>
                          <td className="px-2 py-2 text-right sm:px-3">
                            <div className="flex justify-end gap-1.5">
                              <Button
                                variant="default"
                                size="sm"
                                className="px-3"
                                onClick={() =>
                                  ingestMutation.mutate({
                                    text: buildQuickAddEntryText(quickAddDay, quickAddWorkout, quickAddActivityType),
                                    source: 'inline-row',
                                  })
                                }
                                disabled={ingestMutation.isPending || !quickAddDay.trim() || !quickAddWorkout.trim()}
                              >
                                Add
                              </Button>
                            </div>
                          </td>
                        </tr>
                        {selectedRows.map((row) => {
                          const rowKey = `${row.day_utc}-${row.line_no}`;
                          const workoutText = editValues[rowKey] ?? '';
                          const isDirty = workoutText !== row.workout_text;
                          const isPendingDelete =
                            pendingDelete?.row.day_utc === row.day_utc && pendingDelete.row.line_no === row.line_no;
                          const isSavingRow =
                            workoutUpdateMutation.isPending
                            && workoutUpdateMutation.variables?.dayUtc === row.day_utc
                            && workoutUpdateMutation.variables?.lineNo === row.line_no;
                          return (
                            <tr key={rowKey} className={`border-t border-white/10 ${isPendingDelete ? 'bg-rose-500/8' : ''}`}>
                              <td className="px-2 py-2 sm:px-3">
                                <input
                                  className="h-4 w-4 accent-sky-400"
                                  type="checkbox"
                                  checked={row.manual_done}
                                  disabled={isPendingDelete}
                                  onChange={(event) =>
                                    manualDoneMutation.mutate({
                                      dayUtc: row.day_utc,
                                      lineNo: row.line_no,
                                      manualDone: event.target.checked,
                                    })
                                  }
                                />
                              </td>
                              <td className="px-2 py-2 whitespace-nowrap sm:px-3" title={dayLabel(row.day_utc)}>
                                {compactDayLabel(row.day_utc)}
                              </td>
                              <td className="px-2 py-2 sm:px-3">{row.activity}</td>
                              <td className="px-2 py-2 sm:px-3">
                                <input
                                  className={`min-w-[260px] w-full rounded-xl border px-3 py-2 text-sm outline-none transition ${isPendingDelete ? 'border-rose-400/20 bg-rose-500/8 text-slate-400' : 'border-white/10 bg-black/20 text-foreground focus:border-sky-300/40 focus:ring-2 focus:ring-sky-300/20'}`}
                                  value={workoutText}
                                  disabled={isPendingDelete}
                                  onChange={(event) => {
                                    setEditValues((previous) => ({ ...previous, [rowKey]: event.target.value }));
                                    setRowSaveResults((previous) => {
                                      if (!(rowKey in previous)) return previous;
                                      const next = { ...previous };
                                      delete next[rowKey];
                                      return next;
                                    });
                                  }}
                                />
                                {rowSaveResults[rowKey] ? (
                                  <p
                                    className={`mt-1 text-xs ${
                                      rowSaveResults[rowKey]?.tone === 'error' ? 'text-red-400' : 'text-slate-300/72'
                                    }`}
                                  >
                                    {rowSaveResults[rowKey]?.message}
                                  </p>
                                ) : null}
                                {isPendingDelete ? <p className="mt-1 text-xs text-rose-200/85">Delete pending. Undo is available in Actions.</p> : null}
                              </td>
                              <td className="px-2 py-2 text-right sm:px-3">{Math.round(row.tss)}</td>
                              <td className="px-2 py-2 text-right sm:px-3">{Math.round(row.rtss)}</td>
                              <td className="px-2 py-2 text-right sm:px-3">{row.distance_eqv_km.toFixed(1)} km</td>
                              <td className="px-2 py-2 text-right sm:px-3">{row.if_proxy_pct.toFixed(0)}%</td>
                              <td className="px-2 py-2 text-right sm:px-3">
                                <div className="flex justify-end gap-1.5">
                                  <Button
                                    variant={isDirty ? 'default' : 'outline'}
                                    size="sm"
                                    className={isDirty ? 'px-2.5' : 'border-white/10 px-2.5 text-slate-200 hover:bg-white/10 hover:text-white'}
                                    disabled={!isDirty || isSavingRow || isPendingDelete}
                                    onClick={() =>
                                      workoutUpdateMutation.mutate({
                                        dayUtc: row.day_utc,
                                        lineNo: row.line_no,
                                        workoutText,
                                        manualDone: row.manual_done,
                                      })
                                    }
                                  >
                                    {isSavingRow ? 'Saving...' : isDirty ? 'Save' : 'Saved'}
                                  </Button>
                                  {isPendingDelete ? (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="border-amber-200/40 px-2.5 text-amber-50 hover:bg-amber-500/15"
                                      onClick={handleUndoDelete}
                                    >
                                      Undo
                                    </Button>
                                  ) : (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="border-rose-400/25 px-2.5 text-rose-100 hover:bg-rose-500/12 hover:text-rose-50"
                                      onClick={() => queueDelete(row)}
                                    >
                                      Delete
                                    </Button>
                                  )}
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                        {selectedRows.length === 0 ? (
                          <tr>
                            <td colSpan={9} className="px-3 py-6 text-center text-sm text-slate-300/60">
                              No planned activities in the selected week.
                            </td>
                          </tr>
                        ) : null}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </>
      ) : null}
    </section>
  );
}
