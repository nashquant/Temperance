import { useEffect, useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { useSettingsQuery } from '@/features/settings/hooks/use-settings-query';
import { updateSettings } from '@/features/settings/services/settings-api';
import type { InjuryWindow, LthrCurvePoint, LtPaceCurvePoint, SpecificityProfile } from '@/features/settings/types/settings';
import { queryClient } from '@/lib/query-client';

interface LthrDraftRow {
  id: string;
  date: string;
  lthr_bpm: number;
}

interface LtPaceDraftRow {
  id: string;
  date: string;
  lt_pace_sec_per_km: number;
}

interface InjuryDraftRow {
  id: string;
  label: string;
  start: string;
  end: string;
  severity: 'injury' | 'light_injury';
}

function rowId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function SettingsPage(): JSX.Element {
  const { session, profile } = useAuth();
  const query = useSettingsQuery();

  const [ifZones, setIfZones] = useState({ z1_max: 0.7, z2_max: 0.8, z3_max: 0.9, z4_max: 1.0 });
  const [specificity, setSpecificity] = useState<SpecificityProfile>({ non_running: 0.8, treadmill: 1.0, elliptical: 0.8, cycling: 0.8 });
  const [lthrRows, setLthrRows] = useState<LthrDraftRow[]>([]);
  const [paceRows, setPaceRows] = useState<LtPaceDraftRow[]>([]);
  const [injuryRows, setInjuryRows] = useState<InjuryDraftRow[]>([]);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!query.data) return;
    setIfZones(query.data.if_zone_thresholds);
    setSpecificity(query.data.specificity_profile);
    setLthrRows(
      query.data.lthr_curve.map((row) => ({ id: rowId(), date: row.date, lthr_bpm: Number(row.lthr_bpm) || 0 })),
    );
    setPaceRows(
      query.data.lt_pace_curve.map((row) => ({ id: rowId(), date: row.date, lt_pace_sec_per_km: Number(row.lt_pace_sec_per_km) || 0 })),
    );
    setInjuryRows(
      query.data.injury_windows.map((row) => ({
        id: rowId(),
        label: row.label,
        start: row.start,
        end: row.end,
        severity: row.severity,
      })),
    );
  }, [query.data]);

  const saveMutation = useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      if (!session?.token) throw new Error('Missing auth token');
      return updateSettings({
        token: session.token,
        owner: profile?.owner,
        payload,
      });
    },
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ['settings'] });
      setSaveMsg(`Saved: ${result.updated.join(', ') || 'no changes'}`);
    },
    onError: (error) => {
      setSaveMsg(error instanceof Error ? error.message : 'Unable to save settings.');
    },
  });

  const parsedCurves = useMemo(() => {
    const lthr: LthrCurvePoint[] = lthrRows
      .filter((row) => row.date)
      .map((row) => ({ date: row.date, lthr_bpm: Number(row.lthr_bpm) || 0 }))
      .sort((a, b) => a.date.localeCompare(b.date));

    const pace: LtPaceCurvePoint[] = paceRows
      .filter((row) => row.date)
      .map((row) => ({ date: row.date, lt_pace_sec_per_km: Number(row.lt_pace_sec_per_km) || 0 }))
      .sort((a, b) => a.date.localeCompare(b.date));

    const injury: InjuryWindow[] = injuryRows
      .filter((row) => row.label.trim() && row.start && row.end)
      .map((row) => ({
        label: row.label.trim(),
        start: row.start,
        end: row.end,
        severity: row.severity,
      }))
      .sort((a, b) => a.start.localeCompare(b.start));

    return { lthr, pace, injury };
  }, [injuryRows, lthrRows, paceRows]);

  if (query.isLoading) {
    return (
      <section className="space-y-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-56 w-full" />
        <Skeleton className="h-56 w-full" />
      </section>
    );
  }

  if (query.isError) {
    return (
      <Alert className="border-red-300 text-red-700 dark:border-red-900 dark:text-red-300">
        <AlertTitle>Unable to load settings</AlertTitle>
        <AlertDescription>{query.error instanceof Error ? query.error.message : 'Unexpected error.'}</AlertDescription>
      </Alert>
    );
  }

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">Mirrors v1 User Inputs for training model controls.</p>
      </div>

      {saveMsg ? <p className="text-sm text-muted-foreground">{saveMsg}</p> : null}

      <Card>
        <CardContent className="space-y-4 p-4">
          <p className="text-sm font-medium">IF Zones (fractions)</p>
          <div className="grid gap-3 md:grid-cols-4">
            {(['z1_max', 'z2_max', 'z3_max', 'z4_max'] as const).map((key) => (
              <div key={key}>
                <p className="mb-1 text-xs text-muted-foreground">{key}</p>
                <Input
                  type="number"
                  step="0.01"
                  value={ifZones[key]}
                  onChange={(event) => setIfZones((previous) => ({ ...previous, [key]: Number(event.target.value) }))}
                />
              </div>
            ))}
          </div>
          <Button onClick={() => saveMutation.mutate({ if_zone_thresholds: ifZones })} disabled={saveMutation.isPending}>Save IF Zones</Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-4 p-4">
          <p className="text-sm font-medium">Specificity Factors</p>
          <div className="grid gap-3 md:grid-cols-4">
            {(['non_running', 'treadmill', 'elliptical', 'cycling'] as const).map((key) => (
              <div key={key}>
                <p className="mb-1 text-xs text-muted-foreground">{key.replace('_', ' ')}</p>
                <Input
                  type="number"
                  step="0.01"
                  value={specificity[key]}
                  onChange={(event) => setSpecificity((previous) => ({ ...previous, [key]: Number(event.target.value) }))}
                />
              </div>
            ))}
          </div>
          <Button onClick={() => saveMutation.mutate({ specificity_profile: specificity })} disabled={saveMutation.isPending}>Save Specificity</Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3 p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">LTHR Curve</p>
            <Button
              variant="outline"
              onClick={() => setLthrRows((previous) => [...previous, { id: rowId(), date: '', lthr_bpm: 0 }])}
              disabled={saveMutation.isPending}
            >
              Add row
            </Button>
          </div>
          <div className="space-y-2">
            {lthrRows.map((row) => (
              <div key={row.id} className="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
                <Input
                  type="date"
                  value={row.date}
                  onChange={(event) =>
                    setLthrRows((previous) => previous.map((item) => (item.id === row.id ? { ...item, date: event.target.value } : item)))
                  }
                />
                <Input
                  type="number"
                  step="1"
                  min={0}
                  value={row.lthr_bpm}
                  onChange={(event) =>
                    setLthrRows((previous) => previous.map((item) => (item.id === row.id ? { ...item, lthr_bpm: Number(event.target.value) } : item)))
                  }
                  placeholder="LTHR bpm"
                />
                <Button
                  variant="outline"
                  onClick={() => setLthrRows((previous) => previous.filter((item) => item.id !== row.id))}
                  disabled={saveMutation.isPending}
                >
                  Remove
                </Button>
              </div>
            ))}
          </div>
          <Button onClick={() => saveMutation.mutate({ lthr_curve: parsedCurves.lthr })} disabled={saveMutation.isPending}>Save LTHR Curve</Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3 p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">LT Pace Curve</p>
            <Button
              variant="outline"
              onClick={() => setPaceRows((previous) => [...previous, { id: rowId(), date: '', lt_pace_sec_per_km: 0 }])}
              disabled={saveMutation.isPending}
            >
              Add row
            </Button>
          </div>
          <div className="space-y-2">
            {paceRows.map((row) => (
              <div key={row.id} className="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
                <Input
                  type="date"
                  value={row.date}
                  onChange={(event) =>
                    setPaceRows((previous) => previous.map((item) => (item.id === row.id ? { ...item, date: event.target.value } : item)))
                  }
                />
                <Input
                  type="number"
                  step="1"
                  min={0}
                  value={row.lt_pace_sec_per_km}
                  onChange={(event) =>
                    setPaceRows((previous) =>
                      previous.map((item) => (item.id === row.id ? { ...item, lt_pace_sec_per_km: Number(event.target.value) } : item)),
                    )
                  }
                  placeholder="LT pace sec/km"
                />
                <Button
                  variant="outline"
                  onClick={() => setPaceRows((previous) => previous.filter((item) => item.id !== row.id))}
                  disabled={saveMutation.isPending}
                >
                  Remove
                </Button>
              </div>
            ))}
          </div>
          <Button onClick={() => saveMutation.mutate({ lt_pace_curve: parsedCurves.pace })} disabled={saveMutation.isPending}>Save LT Pace Curve</Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3 p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">Injury Overlays</p>
            <Button
              variant="outline"
              onClick={() =>
                setInjuryRows((previous) => [
                  ...previous,
                  { id: rowId(), label: '', start: '', end: '', severity: 'light_injury' },
                ])
              }
              disabled={saveMutation.isPending}
            >
              Add row
            </Button>
          </div>
          <div className="space-y-2">
            {injuryRows.map((row) => (
              <div key={row.id} className="grid gap-2 md:grid-cols-[1.2fr_1fr_1fr_1fr_auto]">
                <Input
                  value={row.label}
                  onChange={(event) =>
                    setInjuryRows((previous) => previous.map((item) => (item.id === row.id ? { ...item, label: event.target.value } : item)))
                  }
                  placeholder="Label"
                />
                <Input
                  type="date"
                  value={row.start}
                  onChange={(event) =>
                    setInjuryRows((previous) => previous.map((item) => (item.id === row.id ? { ...item, start: event.target.value } : item)))
                  }
                />
                <Input
                  type="date"
                  value={row.end}
                  onChange={(event) =>
                    setInjuryRows((previous) => previous.map((item) => (item.id === row.id ? { ...item, end: event.target.value } : item)))
                  }
                />
                <Select
                  value={row.severity}
                  onValueChange={(value) =>
                    setInjuryRows((previous) =>
                      previous.map((item) =>
                        item.id === row.id ? { ...item, severity: value as 'injury' | 'light_injury' } : item,
                      ),
                    )
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="light_injury">Light injury</SelectItem>
                    <SelectItem value="injury">Injury</SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  variant="outline"
                  onClick={() => setInjuryRows((previous) => previous.filter((item) => item.id !== row.id))}
                  disabled={saveMutation.isPending}
                >
                  Remove
                </Button>
              </div>
            ))}
          </div>
          <Button onClick={() => saveMutation.mutate({ injury_windows: parsedCurves.injury })} disabled={saveMutation.isPending}>Save Injury Overlays</Button>
        </CardContent>
      </Card>
    </section>
  );
}
