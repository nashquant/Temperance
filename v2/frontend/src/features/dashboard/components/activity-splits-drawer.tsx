import { X } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useActivityDetailQuery } from '@/features/dashboard/hooks/use-activity-detail-query';

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
  const detailQuery = useActivityDetailQuery(open ? activityId : null);

  if (!open) return null;

  const activity = detailQuery.data?.activity;
  const laps = Array.isArray(detailQuery.data?.split_rows)
    ? detailQuery.data?.split_rows
    : [];
  const useEqv = laps.length > 0 && laps.some((lap) => lap.display_mode === 'eqv');

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
