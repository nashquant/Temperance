import { useMutation } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { X } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { useActivityDetailQuery } from '@/features/dashboard/hooks/use-activity-detail-query';
import { updateCustomActivityWorkout } from '@/features/custom-activities/services/custom-activities-api';
import { updatePlannedWorkout } from '@/features/plan-activities/services/plan-activities-api';
import { queryClient } from '@/lib/query-client';

interface ActivitySplitsDrawerProps {
  activityId: string | null;
  open: boolean;
  onClose: () => void;
}

function fmtDurationSeconds(seconds: number): string {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  return `${m}m ${s}s`;
}

export function ActivitySplitsDrawer({
  activityId,
  open,
  onClose,
}: ActivitySplitsDrawerProps): JSX.Element | null {
  const { session, profile } = useAuth();
  const detailQuery = useActivityDetailQuery(open ? activityId : null);
  const [sourceText, setSourceText] = useState('');

  if (!open) return null;

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
  const laps = Array.isArray(detailQuery.data?.split_rows)
    ? detailQuery.data?.split_rows
    : [];
  const useEqv = laps.length > 0 && laps.some((lap) => lap.display_mode === 'eqv');
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

  return (
    <div className="fixed inset-0 z-50 flex">
      <button
        type="button"
        className="h-full flex-1 bg-black/55"
        onClick={onClose}
        aria-label="Close activity details"
      />
      <div className="h-full w-full max-w-[560px] overflow-y-auto border-l border-border/70 bg-background p-4 shadow-2xl">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold">Activity Splits</h3>
            <p className="text-sm text-muted-foreground">
              {activity?.sport_type || '-'} {activity?.date ? `· ${activity.date}` : ''}
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close panel">
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
            <div className="grid grid-cols-2 gap-2 rounded-lg border border-border/70 bg-card/40 p-3 text-sm">
              <div>TSS: <span className="font-semibold">{Math.round(activity?.tss ?? 0)}</span></div>
              <div>rTSS: <span className="font-semibold">{Math.round(activity?.rtss ?? 0)}</span></div>
              <div>Pace: <span className="font-semibold">{activity?.avg_pace_display || '-'}</span></div>
              <div>HR: <span className="font-semibold">{Math.round(activity?.avg_hr ?? 0)} bpm</span></div>
            </div>

            {generatedText ? (
              <div className="space-y-2 rounded-lg border border-border/70 bg-card/30 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-foreground">Generated From</p>
                    <p className="text-xs text-muted-foreground">
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
                  className="min-h-24 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
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
              <div className="rounded-lg border border-border/70 bg-card/30 p-4 text-sm text-muted-foreground">
                No split laps available for this activity.
              </div>
            ) : (
              <div className="overflow-hidden rounded-lg border border-border/70">
                <table className="w-full text-sm">
                  <thead className="bg-card/70 text-muted-foreground">
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
                      <tr key={`${lap.lap ?? index}-${index}`} className="border-t border-border/60">
                        <td className="px-3 py-2">{lap.lap ?? index + 1}</td>
                        <td className="px-3 py-2">{lap.description || '-'}</td>
                        <td className="px-3 py-2">{lap.duration_label || fmtDurationSeconds(0)}</td>
                        <td className="px-3 py-2">
                          {Number(useEqv ? lap.distance_eqv_km : lap.distance_km).toFixed(2)} km
                        </td>
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
