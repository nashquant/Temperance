import { useMutation } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Clock3, HeartPulse, Route, Target, X } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TooltipProps } from 'recharts';
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { useActivityDetailQuery } from '@/features/dashboard/hooks/use-activity-detail-query';
import type { ActivityDetailResponse } from '@/features/dashboard/types/activity-detail';
import { updateCustomActivityWorkout } from '@/features/custom-activities/services/custom-activities-api';
import { updatePlannedWorkout } from '@/features/plan-activities/services/plan-activities-api';
import { queryClient } from '@/lib/query-client';

interface ActivitySplitsDrawerProps {
  activityId: string | null;
  open: boolean;
  onClose: () => void;
}

type DrawerLapRow = {
  lap: number;
  description: string;
  duration_label: string;
  duration_seconds?: number;
  avg_hr: number;
  if_pct: number;
  distance_km: number;
  distance_eqv_km: number;
  pace_label: string;
  pace_eqv_label: string;
  display_mode: 'running' | 'eqv';
};

function fmtDurationSeconds(seconds: number): string {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  return `${m}m ${s}s`;
}

function paceLabelFromSpeed(speed: number): string {
  const numeric = Number(speed) || 0;
  if (numeric <= 0) return '-';
  const secondsPerKm = 1000 / numeric;
  const minutes = Math.floor(secondsPerKm / 60);
  const seconds = Math.round(secondsPerKm % 60);
  return `${minutes}:${String(seconds).padStart(2, '0')}/km`;
}

function parseDurationLabelSeconds(label: string): number {
  const raw = String(label || '').trim().toLowerCase();
  if (!raw) return 0;
  const hourMatch = raw.match(/(\d+)\s*h/);
  const minuteMatch = raw.match(/(\d+)\s*m/);
  const secondMatch = raw.match(/(\d+)\s*s/);
  const hours = Number(hourMatch?.[1] || 0);
  const minutes = Number(minuteMatch?.[1] || 0);
  const seconds = Number(secondMatch?.[1] || 0);
  return hours * 3600 + minutes * 60 + seconds;
}

function splitBarColor(ifPct: number): string {
  if (ifPct >= 100) return '#f43f5e';
  if (ifPct >= 90) return '#f97316';
  if (ifPct >= 80) return '#facc15';
  if (ifPct >= 65) return '#38bdf8';
  return '#22c55e';
}

function SplitBarTooltip({
  active,
  payload,
}: TooltipProps<ValueType, NameType>): JSX.Element | null {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload as
    | {
        lap_label: string;
        if_pct: number;
        duration_label: string;
        duration_ratio: number;
      }
    | undefined;
  if (!row) return null;

  return (
    <div className="min-w-[170px] rounded-xl border border-sky-300/15 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_45%),linear-gradient(180deg,rgba(15,23,42,0.94),rgba(2,6,23,0.98))] p-3 shadow-2xl backdrop-blur">
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-sky-200/78">{row.lap_label}</p>
      <div className="space-y-1.5 text-xs">
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-300/72">Duration</span>
          <span className="font-semibold text-foreground">{row.duration_label}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-300/72">IF</span>
          <span className="font-semibold text-foreground">{Math.round(Number(row.if_pct) || 0)}%</span>
        </div>
      </div>
    </div>
  );
}

function SplitDurationShape(props: {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  payload?: { duration_ratio?: number; if_pct?: number };
}): JSX.Element {
  const x = Number(props.x || 0);
  const y = Number(props.y || 0);
  const width = Number(props.width || 0);
  const height = Number(props.height || 0);
  const durationRatio = Math.max(0.18, Math.min(1, Number(props.payload?.duration_ratio || 0.18)));
  const actualWidth = width * durationRatio;
  const insetX = x + (width - actualWidth) / 2;
  const fill = splitBarColor(Number(props.payload?.if_pct || 0));

  return (
    <g>
      <rect
        x={insetX}
        y={y}
        width={actualWidth}
        height={height}
        rx={8}
        ry={8}
        fill="rgba(255,255,255,0.04)"
        stroke="rgba(255,255,255,0.06)"
      />
      <rect
        x={insetX}
        y={y}
        width={actualWidth}
        height={height}
        rx={8}
        ry={8}
        fill={fill}
        fillOpacity={0.92}
      />
      <rect
        x={insetX}
        y={y}
        width={actualWidth}
        height={Math.min(18, height * 0.22)}
        rx={8}
        ry={8}
        fill="rgba(255,255,255,0.16)"
      />
    </g>
  );
}

function normalizedLapRows(detail: ActivityDetailResponse | undefined): DrawerLapRow[] {
  if (Array.isArray(detail?.split_rows) && detail.split_rows.length > 0) {
    return detail.split_rows.map((row) => ({
      ...row,
      duration_seconds: row.duration_seconds ?? parseDurationLabelSeconds(row.duration_label),
    }));
  }

  const rawLaps = detail?.splits?.split?.lapDTOs;
  if (!Array.isArray(rawLaps) || rawLaps.length === 0) return [];

  const sportType = String(detail?.activity?.sport_type || '').toLowerCase();
  const runningLike = sportType.includes('run') || sportType.includes('treadmill');

  return rawLaps
    .map((lap, index) => {
      const duration = Number(lap?.duration ?? lap?.elapsedDuration ?? 0) || 0;
      const distanceKm = (Number(lap?.distance) || 0) / 1000;
      const avgHr = Number(lap?.averageHR) || 0;
      const avgSpeed = Number(lap?.averageSpeed) || 0;
      return {
        lap: Number(lap?.lapIndex) || index + 1,
        description: '-',
        duration_label: fmtDurationSeconds(duration),
        duration_seconds: duration,
        avg_hr: avgHr,
        if_pct: 0,
        distance_km: distanceKm,
        distance_eqv_km: distanceKm,
        pace_label: paceLabelFromSpeed(avgSpeed),
        pace_eqv_label: paceLabelFromSpeed(avgSpeed),
        display_mode: runningLike ? ('running' as const) : ('eqv' as const),
      };
    })
    .filter((lap) => lap.duration_label !== fmtDurationSeconds(0) || lap.distance_km > 0);
}

export function ActivitySplitsDrawer({
  activityId,
  open,
  onClose,
}: ActivitySplitsDrawerProps): JSX.Element | null {
  const { session, profile } = useAuth();
  const detailQuery = useActivityDetailQuery(open && activityId ? activityId : null);
  const [sourceText, setSourceText] = useState('');

  const activity = detailQuery.data?.activity;
  const sourceKind = String(detailQuery.data?.details?.source || '').trim().toLowerCase();
  const raw = detailQuery.data?.raw;
  const rawDayUtc = String(raw?.day_utc || '').trim();
  const rawLineNo = Number(raw?.line_no || 0);
  const generatedText =
    sourceKind === 'planned'
      ? String(raw?.workout_text || '').trim()
      : sourceKind === 'custom'
        ? String(raw?.activity_text || '').trim()
        : '';
  const canEditGeneratedText = Boolean(
    (sourceKind === 'planned' || sourceKind === 'custom') && rawDayUtc && rawLineNo > 0,
  );
  const laps = normalizedLapRows(detailQuery.data);
  const useEqv = laps.length > 0 && laps.some((lap) => lap.display_mode === 'eqv');
  const maxDurationSeconds = Math.max(...laps.map((lap) => Number(lap.duration_seconds) || parseDurationLabelSeconds(lap.duration_label)), 0);
  const splitChartData = laps.map((lap) => {
    const durationSeconds = Number(lap.duration_seconds) || parseDurationLabelSeconds(lap.duration_label);
    return {
      lap_label: `Lap ${lap.lap}`,
      if_pct: Number(lap.if_pct) || 0,
      duration_label: lap.duration_label,
      duration_ratio: maxDurationSeconds > 0 ? durationSeconds / maxDurationSeconds : 0.18,
    };
  });

  const updateMutation = useMutation({
    mutationFn: async (nextText: string) => {
      if (!session?.token) throw new Error('Missing auth token');
      if (!rawDayUtc || rawLineNo <= 0) throw new Error('Missing activity reference');
      const trimmed = nextText.trim();
      if (!trimmed) throw new Error('Activity text cannot be empty');

      if (sourceKind === 'planned') {
        await updatePlannedWorkout({
          token: session.token,
          owner: profile?.owner,
          dayUtc: rawDayUtc,
          lineNo: rawLineNo,
          workoutText: trimmed,
        });
        return;
      }

      if (sourceKind === 'custom') {
        await updateCustomActivityWorkout({
          token: session.token,
          owner: profile?.owner,
          dayUtc: rawDayUtc,
          lineNo: rawLineNo,
          activityText: trimmed,
        });
        return;
      }

      throw new Error('This activity cannot be edited here');
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['activity-detail', profile?.owner, activityId] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['planned-activities'] }),
        queryClient.invalidateQueries({ queryKey: ['custom-activities'] }),
        queryClient.invalidateQueries({ queryKey: ['week-outlook'] }),
      ]);
    },
  });

  useEffect(() => {
    setSourceText(generatedText);
  }, [generatedText, activityId]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <button
        type="button"
        className="h-full flex-1 bg-black/60 backdrop-blur-[2px]"
        onClick={onClose}
        aria-label="Close activity details"
      />
      <div className="h-full w-full max-w-[620px] overflow-y-auto border-l border-sky-300/12 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_38%),linear-gradient(180deg,rgba(15,23,42,0.96),rgba(2,6,23,0.99))] p-4 shadow-[0_24px_80px_rgba(0,0,0,0.45)]">
        <div className="mb-4 flex items-start justify-between gap-3 border-b border-white/8 pb-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-200/80">Activity Details</p>
            <h3 className="text-lg font-semibold text-foreground">Splits</h3>
            <p className="text-sm text-slate-300/72">
              {activity?.sport_type || '-'} {activity?.date ? `· ${activity.date}` : ''}
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close panel" className="text-slate-300/80 hover:text-white">
            <X className="h-4 w-4" />
          </Button>
        </div>

        {detailQuery.isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-56 w-full" />
          </div>
        ) : null}

        {detailQuery.isError ? (
          <Alert className="border-red-500/40 text-red-300">
            <AlertTitle>Unable to load activity details</AlertTitle>
            <AlertDescription>
              {detailQuery.error instanceof Error ? detailQuery.error.message : 'Unexpected error.'}
            </AlertDescription>
          </Alert>
        ) : null}

        {!detailQuery.isLoading && !detailQuery.isError && detailQuery.data ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="rounded-xl border border-white/10 bg-black/15 p-3">
                <p className="inline-flex items-center gap-1 text-xs text-slate-300/72"><Target className="h-3 w-3" />TSS</p>
                <p className="mt-1 font-semibold text-foreground">{Math.round(activity?.tss ?? 0)}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/15 p-3">
                <p className="inline-flex items-center gap-1 text-xs text-slate-300/72"><Target className="h-3 w-3" />rTSS</p>
                <p className="mt-1 font-semibold text-foreground">{Math.round(activity?.rtss ?? 0)}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/15 p-3">
                <p className="inline-flex items-center gap-1 text-xs text-slate-300/72"><Route className="h-3 w-3" />Pace</p>
                <p className="mt-1 font-semibold text-foreground">{activity?.avg_pace_display || '-'}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/15 p-3">
                <p className="inline-flex items-center gap-1 text-xs text-slate-300/72"><HeartPulse className="h-3 w-3" />HR</p>
                <p className="mt-1 font-semibold text-foreground">{Math.round(activity?.avg_hr ?? 0)} bpm</p>
              </div>
            </div>

            {generatedText ? (
              <div className="space-y-2 rounded-xl border border-white/10 bg-black/15 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-foreground">Generated From</p>
                    <p className="text-xs text-slate-300/72">
                      {canEditGeneratedText ? 'Edit the source string and resave to regenerate these splits.' : 'Source string used to generate this activity.'}
                    </p>
                  </div>
                  {canEditGeneratedText ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => updateMutation.mutate(sourceText)}
                      disabled={updateMutation.isPending || sourceText.trim() === generatedText}
                    >
                      {updateMutation.isPending ? 'Saving...' : 'Save'}
                    </Button>
                  ) : null}
                </div>
                <textarea
                  className="min-h-24 w-full rounded-xl border border-white/10 bg-black/20 px-3 py-3 text-sm text-foreground outline-none transition focus:border-sky-300/40 focus:ring-2 focus:ring-sky-300/20 disabled:cursor-not-allowed disabled:opacity-60"
                  value={sourceText}
                  onChange={(event) => setSourceText(event.target.value)}
                  readOnly={!canEditGeneratedText}
                  disabled={!canEditGeneratedText || updateMutation.isPending}
                />
                {updateMutation.isError ? (
                  <p className="text-sm text-red-400">
                    {updateMutation.error instanceof Error ? updateMutation.error.message : 'Unable to update activity.'}
                  </p>
                ) : null}
              </div>
            ) : null}

            {laps.length === 0 ? (
              <div className="rounded-xl border border-white/10 bg-black/15 p-4 text-sm text-slate-300/72">
                No split laps available for this activity.
              </div>
            ) : (
              <div className="space-y-3">
                <div className="overflow-hidden rounded-xl border border-white/10 bg-black/15 p-3">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-foreground">Split Profile</p>
                      <p className="text-xs text-slate-300/72">Each bar is a lap fingerprint: taller means harder, wider means longer.</p>
                    </div>
                  </div>
                  <div className="rounded-[20px] border border-white/8 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.08),transparent_52%),linear-gradient(180deg,rgba(2,6,23,0.82),rgba(15,23,42,0.6))] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
                    <div className="mb-3 flex flex-wrap gap-2 text-[11px]">
                      {splitChartData.map((row) => (
                        <div key={`chip-${row.lap_label}`} className="rounded-full border border-white/8 bg-white/5 px-2.5 py-1 text-slate-300/76">
                          {row.lap_label}
                        </div>
                      ))}
                    </div>
                  <div className="h-[220px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={splitChartData} barCategoryGap="18%">
                        <CartesianGrid strokeDasharray="3 3" vertical={false} horizontal={false} stroke="rgba(125,211,252,0.1)" />
                        <XAxis
                          dataKey="lap_label"
                          hide
                        />
                        <YAxis
                          domain={[0, 110]}
                          hide
                        />
                        <Tooltip content={<SplitBarTooltip />} cursor={{ fill: 'rgba(56, 189, 248, 0.08)' }} />
                        <Bar dataKey="if_pct" radius={[8, 8, 0, 0]} shape={<SplitDurationShape />}>
                          {splitChartData.map((row) => (
                            <Cell key={row.lap_label} fill={splitBarColor(row.if_pct)} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  </div>
                </div>

                <div className="overflow-hidden rounded-xl border border-white/10 bg-black/15">
                  <div className="flex items-center gap-2 border-b border-white/10 px-3 py-2 text-xs text-slate-300/72">
                  <Clock3 className="h-3 w-3" />
                  <span>{laps.length} split{laps.length === 1 ? '' : 's'}</span>
                </div>
                <table className="w-full text-sm">
                  <thead className="bg-white/5 text-slate-300/72">
                    <tr>
                      <th className="px-3 py-2 text-left">LAP</th>
                      <th className="px-3 py-2 text-left">Type</th>
                      <th className="px-3 py-2 text-left">Time</th>
                      <th className="px-3 py-2 text-left">{useEqv ? 'Dist(E)' : 'Dist'}</th>
                      <th className="px-3 py-2 text-left">{useEqv ? 'Pace(E)' : 'Pace'}</th>
                      <th className="px-3 py-2 text-left">HR</th>
                      <th className="px-3 py-2 text-left">IF</th>
                    </tr>
                  </thead>
                  <tbody>
                    {laps.map((lap, index) => (
                      <tr key={`${lap.lap ?? index}-${index}`} className="border-t border-white/10 text-foreground/94">
                        <td className="px-3 py-2">{lap.lap ?? index + 1}</td>
                        <td className="px-3 py-2">{lap.description || '-'}</td>
                        <td className="px-3 py-2">{lap.duration_label || fmtDurationSeconds(0)}</td>
                        <td className="px-3 py-2">{Number(useEqv ? lap.distance_eqv_km : lap.distance_km).toFixed(2)} km</td>
                        <td className="px-3 py-2">{useEqv ? lap.pace_eqv_label : lap.pace_label}</td>
                        <td className="px-3 py-2">{Math.round(Number(lap.avg_hr) || 0)}</td>
                        <td className="px-3 py-2">{Math.round(Number(lap.if_pct) || 0)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
