import { useEffect, useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { useSettingsQuery } from '@/features/settings/hooks/use-settings-query';
import { updateSettings } from '@/features/settings/services/settings-api';
import type { InjuryWindow, LthrCurvePoint, LtPaceCurvePoint, SpecificityProfile } from '@/features/settings/types/settings';
import { queryClient } from '@/lib/query-client';

function toPrettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function parseJsonArray<T>(raw: string, fallback: T[]): T[] {
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as T[]) : fallback;
  } catch {
    return fallback;
  }
}

export function SettingsPage(): JSX.Element {
  const { session, profile } = useAuth();
  const query = useSettingsQuery();

  const [ifZones, setIfZones] = useState({ z1_max: 0.7, z2_max: 0.8, z3_max: 0.9, z4_max: 1.0 });
  const [specificity, setSpecificity] = useState<SpecificityProfile>({ non_running: 0.8, treadmill: 1.0, elliptical: 0.8, cycling: 0.8 });
  const [lthrRaw, setLthrRaw] = useState('[]');
  const [paceRaw, setPaceRaw] = useState('[]');
  const [injuryRaw, setInjuryRaw] = useState('[]');
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!query.data) return;
    setIfZones(query.data.if_zone_thresholds);
    setSpecificity(query.data.specificity_profile);
    setLthrRaw(toPrettyJson(query.data.lthr_curve));
    setPaceRaw(toPrettyJson(query.data.lt_pace_curve));
    setInjuryRaw(toPrettyJson(query.data.injury_windows));
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
    const lthr = parseJsonArray<LthrCurvePoint>(lthrRaw, []);
    const pace = parseJsonArray<LtPaceCurvePoint>(paceRaw, []);
    const injury = parseJsonArray<InjuryWindow>(injuryRaw, []);
    return { lthr, pace, injury };
  }, [injuryRaw, lthrRaw, paceRaw]);

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
          <p className="text-sm font-medium">LTHR Curve (JSON array)</p>
          <textarea className="min-h-[120px] w-full rounded-md border border-input bg-transparent p-2 font-mono text-xs" value={lthrRaw} onChange={(event) => setLthrRaw(event.target.value)} />
          <Button onClick={() => saveMutation.mutate({ lthr_curve: parsedCurves.lthr })} disabled={saveMutation.isPending}>Save LTHR Curve</Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3 p-4">
          <p className="text-sm font-medium">LT Pace Curve (JSON array)</p>
          <textarea className="min-h-[120px] w-full rounded-md border border-input bg-transparent p-2 font-mono text-xs" value={paceRaw} onChange={(event) => setPaceRaw(event.target.value)} />
          <Button onClick={() => saveMutation.mutate({ lt_pace_curve: parsedCurves.pace })} disabled={saveMutation.isPending}>Save LT Pace Curve</Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3 p-4">
          <p className="text-sm font-medium">Injury Overlays (JSON array)</p>
          <textarea className="min-h-[120px] w-full rounded-md border border-input bg-transparent p-2 font-mono text-xs" value={injuryRaw} onChange={(event) => setInjuryRaw(event.target.value)} />
          <Button onClick={() => saveMutation.mutate({ injury_windows: parsedCurves.injury })} disabled={saveMutation.isPending}>Save Injury Overlays</Button>
        </CardContent>
      </Card>
    </section>
  );
}
