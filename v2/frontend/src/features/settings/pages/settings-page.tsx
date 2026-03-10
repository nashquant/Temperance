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
import type { LthrCurvePoint, LtPaceCurvePoint, SpecificityProfile } from '@/features/settings/types/settings';
import { queryClient } from '@/lib/query-client';

interface LthrDraftRow {
  id: string;
  date: string;
  lthr_bpm: number;
}

interface LtPaceDraftRow {
  id: string;
  date: string;
  pace_input: string;
}

function rowId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function secondsToPaceInput(seconds: number): string {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value <= 0) return '';
  const mm = Math.floor(value / 60);
  const ss = Math.round(value % 60);
  return `${mm}:${String(ss).padStart(2, '0')}`;
}

function parsePaceInputToSeconds(raw: string): number | null {
  const value = String(raw || '').trim().toLowerCase();
  if (!value) return null;

  const normalized = value.replace('/km', '').replace(/\s+/g, '');
  if (/^\d{1,2}:\d{2}$/.test(normalized)) {
    const [mStr, sStr] = normalized.split(':');
    const minutes = Number(mStr);
    const seconds = Number(sStr);
    if (!Number.isFinite(minutes) || !Number.isFinite(seconds) || minutes < 0 || seconds < 0 || seconds >= 60) {
      return null;
    }
    return minutes * 60 + seconds;
  }

  if (/^\d+(\.\d+)?$/.test(normalized)) {
    const asNumber = Number(normalized);
    return Number.isFinite(asNumber) && asNumber > 0 ? asNumber : null;
  }

  return null;
}

function formatPace(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return '-';
  const total = Math.round(seconds);
  const mm = Math.floor(total / 60);
  const ss = total % 60;
  return `${mm}:${String(ss).padStart(2, '0')}/km`;
}

function formatIfZoneLabel(key: 'z1_max' | 'z2_max' | 'z3_max' | 'z4_max'): string {
  const zone = key.replace('_max', '').toUpperCase().replace('Z', 'Zone ');
  return `${zone} Ceiling`;
}

function formatSpecificityLabel(key: keyof SpecificityProfile): string {
  if (key === 'non_running') return 'Non-Running';
  return key.charAt(0).toUpperCase() + key.slice(1);
}

export function SettingsPage(): JSX.Element {
  const surfaceClassName =
    'overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]';
  const controlButtonClassName =
    'h-10 rounded-xl border border-white/10 bg-[linear-gradient(180deg,rgba(30,41,59,0.88),rgba(15,23,42,0.96))] px-4 text-[12px] font-medium text-slate-100 shadow-[0_8px_18px_rgba(2,6,23,0.22)] hover:border-white/16 hover:bg-[linear-gradient(180deg,rgba(51,65,85,0.92),rgba(15,23,42,0.98))]';
  const fieldLabelClassName = 'mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74';
  const fieldHintClassName = 'text-[11px] text-slate-300/58';
  const { session, profile } = useAuth();
  const query = useSettingsQuery();

  const [ifZones, setIfZones] = useState({ z1_max: 0.7, z2_max: 0.8, z3_max: 0.9, z4_max: 1.0 });
  const [specificity, setSpecificity] = useState<SpecificityProfile>({ non_running: 0.8, treadmill: 1.0, elliptical: 0.8, cycling: 0.8 });
  const [lthrRows, setLthrRows] = useState<LthrDraftRow[]>([]);
  const [paceRows, setPaceRows] = useState<LtPaceDraftRow[]>([]);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!query.data) return;
    setIfZones(query.data.if_zone_thresholds);
    setSpecificity(query.data.specificity_profile);
    setLthrRows(
      query.data.lthr_curve.map((row) => ({ id: rowId(), date: row.date, lthr_bpm: Number(row.lthr_bpm) || 0 })),
    );
    setPaceRows(
      query.data.lt_pace_curve.map((row) => ({
        id: rowId(),
        date: row.date,
        pace_input: secondsToPaceInput(Number(row.lt_pace_sec_per_km) || 0),
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

    let paceError: string | null = null;
    const pace: LtPaceCurvePoint[] = [];
    for (const row of paceRows) {
      const hasDate = Boolean(row.date);
      const hasPace = Boolean(String(row.pace_input || '').trim());
      if (!hasDate && !hasPace) continue;
      if (!hasDate || !hasPace) {
        paceError = 'Each LT Pace row must have both date and pace.';
        break;
      }
      const paceSeconds = parsePaceInputToSeconds(row.pace_input);
      if (paceSeconds === null) {
        paceError = `Invalid LT pace "${row.pace_input}". Use formats like 3:30, 3:30/km, or 210.`;
        break;
      }
      pace.push({ date: row.date, lt_pace_sec_per_km: paceSeconds });
    }
    pace.sort((a, b) => a.date.localeCompare(b.date));

    return { lthr, pace, paceError };
  }, [lthrRows, paceRows]);

  const zoneGuide = useMemo(() => {
    const sortedLthr = [...lthrRows]
      .filter((row) => row.date)
      .sort((a, b) => a.date.localeCompare(b.date));
    const sortedPace = [...paceRows]
      .filter((row) => row.date)
      .sort((a, b) => a.date.localeCompare(b.date));

    const latestLthr = sortedLthr.at(-1) ?? null;
    const latestPace = sortedPace.at(-1) ?? null;
    const lthr = latestLthr?.lthr_bpm ?? 0;
    const ltPaceSec = parsePaceInputToSeconds(latestPace?.pace_input ?? '') ?? 0;
    const z1 = Number(ifZones.z1_max) || 0;
    const z2 = Number(ifZones.z2_max) || 0;
    const z3 = Number(ifZones.z3_max) || 0;
    const z4 = Number(ifZones.z4_max) || 0;

    const hrAt = (fraction: number) => Math.round(lthr * fraction);
    const paceAt = (fraction: number) => (fraction > 0 ? ltPaceSec / fraction : 0);
    const pct = (fraction: number) => Math.round(fraction * 100);

    const rows = [
      {
        zone: 'Z1',
        ifRange: `< ${pct(z1)}%`,
        hrRange: `< ${hrAt(z1)}`,
        paceRange: `> ${formatPace(paceAt(z1))}`,
      },
      {
        zone: 'Z2',
        ifRange: `${pct(z1)}% - <${pct(z2)}%`,
        hrRange: `${hrAt(z1)}-${hrAt(z2)}`,
        paceRange: `${formatPace(paceAt(z2))} - ${formatPace(paceAt(z1))}`,
      },
      {
        zone: 'Z3',
        ifRange: `${pct(z2)}% - <${pct(z3)}%`,
        hrRange: `${hrAt(z2)}-${hrAt(z3)}`,
        paceRange: `${formatPace(paceAt(z3))} - ${formatPace(paceAt(z2))}`,
      },
      {
        zone: 'Z4',
        ifRange: `${pct(z3)}% - <${pct(z4)}%`,
        hrRange: `${hrAt(z3)}-${hrAt(z4)}`,
        paceRange: `${formatPace(paceAt(z4))} - ${formatPace(paceAt(z3))}`,
      },
      {
        zone: 'Z5',
        ifRange: `>= ${pct(z4)}%`,
        hrRange: `> ${hrAt(z4)}`,
        paceRange: `< ${formatPace(paceAt(z4))}`,
      },
    ];

    return {
      rows,
      latestLthrDate: latestLthr?.date ?? '',
      latestPaceDate: latestPace?.date ?? '',
      latestLthr: lthr,
      latestPace: latestPace?.pace_input ?? '',
      thresholdsText: `Z1 <${pct(z1)}%, Z2 <${pct(z2)}%, Z3 <${pct(z3)}%, Z4 <${pct(z4)}%, Z5 >=${pct(z4)}%`,
    };
  }, [ifZones.z1_max, ifZones.z2_max, ifZones.z3_max, ifZones.z4_max, lthrRows, paceRows]);

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
      </div>

      {saveMsg ? <p className="text-sm text-muted-foreground">{saveMsg}</p> : null}

      <Card className={surfaceClassName}>
        <CardContent className="space-y-4 p-4">
          <p className="text-sm font-medium">IF Zones (%)</p>
          <div className="grid gap-3 md:grid-cols-4">
            {(['z1_max', 'z2_max', 'z3_max', 'z4_max'] as const).map((key) => (
              <div key={key} className="space-y-1">
                <div>
                  <p className={fieldLabelClassName}>{formatIfZoneLabel(key)}</p>
                  <p className={fieldHintClassName}>% of threshold</p>
                </div>
                <Input
                  type="number"
                  step="1"
                  value={Math.round((Number(ifZones[key]) || 0) * 100)}
                  onChange={(event) =>
                    setIfZones((previous) => ({
                      ...previous,
                      [key]: (Number(event.target.value) || 0) / 100,
                    }))
                  }
                />
              </div>
            ))}
          </div>
          <Button className={controlButtonClassName} onClick={() => saveMutation.mutate({ if_zone_thresholds: ifZones })} disabled={saveMutation.isPending}>Save IF Zones</Button>
        </CardContent>
      </Card>

      <Card className={surfaceClassName}>
        <CardContent className="space-y-3 p-4">
          <p className="text-sm font-medium">IF Zones Guide</p>
          <p className="text-xs text-muted-foreground">
            Using latest values as of {zoneGuide.latestLthrDate || '-'} (LTHR {Math.round(zoneGuide.latestLthr)} bpm, LT pace {zoneGuide.latestPace || '-'}). Current thresholds: {zoneGuide.thresholdsText}.
          </p>
          <div className="overflow-x-auto rounded-xl border border-white/10 bg-black/15">
            <table className="w-full text-sm">
              <thead className="bg-white/5 text-left text-xs text-slate-300/72">
                <tr>
                  <th className="px-3 py-2">Zone</th>
                  <th className="px-3 py-2">IF Range</th>
                  <th className="px-3 py-2">Suggested HR (bpm)</th>
                  <th className="px-3 py-2">Suggested Pace</th>
                </tr>
              </thead>
              <tbody>
                {zoneGuide.rows.map((row) => (
                  <tr key={row.zone} className="border-t border-white/10">
                    <td className="px-3 py-2 font-semibold">{row.zone}</td>
                    <td className="px-3 py-2">{row.ifRange}</td>
                    <td className="px-3 py-2">{row.hrRange}</td>
                    <td className="px-3 py-2">{row.paceRange}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card className={surfaceClassName}>
        <CardContent className="space-y-4 p-4">
          <p className="text-sm font-medium">Specificity Factors</p>
          <div className="grid gap-3 md:grid-cols-4">
            {(['non_running', 'treadmill', 'elliptical', 'cycling'] as const).map((key) => (
              <div key={key} className="space-y-1">
                <div>
                  <p className={fieldLabelClassName}>{formatSpecificityLabel(key)}</p>
                  <p className={fieldHintClassName}>relative % factor</p>
                </div>
                <Input
                  type="number"
                  step="1"
                  value={Math.round((Number(specificity[key]) || 0) * 100)}
                  onChange={(event) =>
                    setSpecificity((previous) => ({
                      ...previous,
                      [key]: (Number(event.target.value) || 0) / 100,
                    }))
                  }
                />
              </div>
            ))}
          </div>
          <Button className={controlButtonClassName} onClick={() => saveMutation.mutate({ specificity_profile: specificity })} disabled={saveMutation.isPending}>Save Specificity</Button>
        </CardContent>
      </Card>

      <Card className={surfaceClassName}>
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
          <Button className={controlButtonClassName} onClick={() => saveMutation.mutate({ lthr_curve: parsedCurves.lthr })} disabled={saveMutation.isPending}>Save LTHR Curve</Button>
        </CardContent>
      </Card>

      <Card className={surfaceClassName}>
        <CardContent className="space-y-3 p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">LT Pace Curve</p>
            <Button
              variant="outline"
              onClick={() => setPaceRows((previous) => [...previous, { id: rowId(), date: '', pace_input: '' }])}
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
                  type="text"
                  value={row.pace_input}
                  onChange={(event) =>
                    setPaceRows((previous) =>
                      previous.map((item) => (item.id === row.id ? { ...item, pace_input: event.target.value } : item)),
                    )
                  }
                  placeholder="e.g. 3:30 or 210"
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
          {parsedCurves.paceError ? <p className="text-xs text-red-400">{parsedCurves.paceError}</p> : null}
          <Button
            className={controlButtonClassName}
            onClick={() => {
              if (parsedCurves.paceError) {
                setSaveMsg(parsedCurves.paceError);
                return;
              }
              saveMutation.mutate({ lt_pace_curve: parsedCurves.pace });
            }}
            disabled={saveMutation.isPending}
          >
            Save LT Pace Curve
          </Button>
        </CardContent>
      </Card>

    </section>
  );
}
