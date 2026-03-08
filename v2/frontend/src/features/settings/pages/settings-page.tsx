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
  pace_input: string;
}

interface InjuryDraftRow {
  id: string;
  label: string;
  start: string;
  end: string;
  severity: 'injury' | 'light_injury';
}

interface IfZoneGuideRow {
  zone: 'Z1' | 'Z2' | 'Z3' | 'Z4' | 'Z5';
  ifRange: string;
  hrRange: string;
  paceRange: string;
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

function pickLatestEffective<T extends { date: string }>(
  rows: T[],
  pickValue: (row: T) => number,
  fallback: number,
): { date: string; value: number } {
  const todayIso = new Date().toISOString().slice(0, 10);
  const sorted = [...rows]
    .filter((row) => row.date)
    .sort((a, b) => a.date.localeCompare(b.date));

  const effective = [...sorted].reverse().find((row) => row.date <= todayIso) ?? sorted.at(-1);
  if (!effective) return { date: todayIso, value: fallback };
  const value = Number(pickValue(effective));
  return { date: effective.date, value: Number.isFinite(value) && value > 0 ? value : fallback };
}

function formatPaceFromSeconds(secPerKm: number): string {
  const value = Number(secPerKm);
  if (!Number.isFinite(value) || value <= 0) return '-';
  const mm = Math.floor(value / 60);
  const ss = Math.round(value % 60);
  return `${mm}:${String(ss).padStart(2, '0')}/km`;
}

function roundInt(value: number): number {
  return Math.round(Number(value) || 0);
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
      query.data.lt_pace_curve.map((row) => ({
        id: rowId(),
        date: row.date,
        pace_input: secondsToPaceInput(Number(row.lt_pace_sec_per_km) || 0),
      })),
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

    const injury: InjuryWindow[] = injuryRows
      .filter((row) => row.label.trim() && row.start && row.end)
      .map((row) => ({
        label: row.label.trim(),
        start: row.start,
        end: row.end,
        severity: row.severity,
      }))
      .sort((a, b) => a.start.localeCompare(b.start));

    return { lthr, pace, injury, paceError };
  }, [injuryRows, lthrRows, paceRows]);

  const ifZoneGuide = useMemo(() => {
    const latestLthr = pickLatestEffective(parsedCurves.lthr, (row) => row.lthr_bpm, 178);
    const latestPace = pickLatestEffective(parsedCurves.pace, (row) => row.lt_pace_sec_per_km, 300);
    const z1 = Number(ifZones.z1_max) || 0.75;
    const z2 = Number(ifZones.z2_max) || 0.85;
    const z3 = Number(ifZones.z3_max) || 0.95;
    const z4 = Number(ifZones.z4_max) || 1.03;
    const hrAt = (intensity: number) => roundInt(latestLthr.value * intensity);
    const paceAt = (intensity: number) => formatPaceFromSeconds(latestPace.value / intensity);

    const rows: IfZoneGuideRow[] = [
      { zone: 'Z1', ifRange: `< ${roundInt(z1 * 100)}%`, hrRange: `< ${hrAt(z1)}`, paceRange: `> ${paceAt(z1)}` },
      {
        zone: 'Z2',
        ifRange: `${roundInt(z1 * 100)}% - <${roundInt(z2 * 100)}%`,
        hrRange: `${hrAt(z1)}-${hrAt(z2)}`,
        paceRange: `${paceAt(z2)} - ${paceAt(z1)}`,
      },
      {
        zone: 'Z3',
        ifRange: `${roundInt(z2 * 100)}% - <${roundInt(z3 * 100)}%`,
        hrRange: `${hrAt(z2)}-${hrAt(z3)}`,
        paceRange: `${paceAt(z3)} - ${paceAt(z2)}`,
      },
      {
        zone: 'Z4',
        ifRange: `${roundInt(z3 * 100)}% - <${roundInt(z4 * 100)}%`,
        hrRange: `${hrAt(z3)}-${hrAt(z4)}`,
        paceRange: `${paceAt(z4)} - ${paceAt(z3)}`,
      },
      { zone: 'Z5', ifRange: `>= ${roundInt(z4 * 100)}%`, hrRange: `> ${hrAt(z4)}`, paceRange: `< ${paceAt(z4)}` },
    ];

    return {
      rows,
      latestDate: latestLthr.date > latestPace.date ? latestLthr.date : latestPace.date,
      latestLthr: roundInt(latestLthr.value),
      latestPaceText: formatPaceFromSeconds(latestPace.value),
      thresholdsText: `Z1 <${roundInt(z1 * 100)}%, Z2 <${roundInt(z2 * 100)}%, Z3 <${roundInt(z3 * 100)}%, Z4 <${roundInt(z4 * 100)}%, Z5 >=${roundInt(z4 * 100)}%`,
    };
  }, [ifZones, parsedCurves.lthr, parsedCurves.pace]);

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
      {saveMsg ? <p className="text-sm text-muted-foreground">{saveMsg}</p> : null}

      <Card>
        <CardContent className="space-y-3 p-4">
          <p className="text-sm font-medium">IF Zones</p>
          <p className="text-xs text-muted-foreground">
            Using latest values as of {ifZoneGuide.latestDate} (LTHR {ifZoneGuide.latestLthr} bpm, LT pace {ifZoneGuide.latestPaceText}). Current thresholds: {ifZoneGuide.thresholdsText}.
          </p>
          <div className="overflow-x-auto rounded border border-border/70">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-left text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Zone</th>
                  <th className="px-3 py-2">IF Range</th>
                  <th className="px-3 py-2">Suggested HR (bpm)</th>
                  <th className="px-3 py-2">Suggested Pace</th>
                </tr>
              </thead>
              <tbody>
                {ifZoneGuide.rows.map((row) => (
                  <tr key={row.zone} className="border-t border-border/70">
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

      <Card>
        <CardContent className="space-y-4 p-4">
          <p className="text-sm font-medium">IF Zones (fractions)</p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {(['z1_max', 'z2_max', 'z3_max', 'z4_max'] as const).map((key) => (
              <div key={key} className="min-w-0">
                <p className="mb-1 text-xs text-muted-foreground">{key} (%)</p>
                <Input
                  type="number"
                  step="0.1"
                  value={Number.isFinite(ifZones[key]) ? (ifZones[key] * 100).toFixed(1).replace(/\.0$/, '') : ''}
                  onChange={(event) =>
                    setIfZones((previous) => ({
                      ...previous,
                      [key]: Number(event.target.value) / 100,
                    }))
                  }
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
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {(['non_running', 'treadmill', 'elliptical', 'cycling'] as const).map((key) => (
              <div key={key} className="min-w-0">
                <p className="mb-1 text-xs text-muted-foreground">{key.replace('_', ' ')} (%)</p>
                <Input
                  type="number"
                  step="0.1"
                  value={Number.isFinite(specificity[key]) ? (specificity[key] * 100).toFixed(1).replace(/\.0$/, '') : ''}
                  onChange={(event) =>
                    setSpecificity((previous) => ({
                      ...previous,
                      [key]: Number(event.target.value) / 100,
                    }))
                  }
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
