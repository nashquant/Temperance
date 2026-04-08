import { useEffect, useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { ChevronDown, Plus, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { CompactDateInput } from '@/components/ui/compact-date-input';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { QueryShell } from '@/components/ui/query-shell';
import {
  FieldLabel,
  SurfaceCard,
  secondaryPageInputClassName,
} from '@/components/ui/secondary-page';

import { useAuth } from '@/features/auth/hooks/use-auth';
import { useSettingsQuery } from '@/features/settings/hooks/use-settings-query';
import { useVdotQuery } from '@/features/settings/hooks/use-vdot-query';
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
  return `Top ${key.replace('_max', '').toUpperCase()}`;
}

function formatSpecificityLabel(key: keyof SpecificityProfile): string {
  if (key === 'non_running') return 'Non-Running';
  return key.charAt(0).toUpperCase() + key.slice(1);
}

const mobileCurveFieldLabelClassName = 'text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-300/58 sm:hidden';

export function SettingsPage(): JSX.Element {
  const addRowButtonClassName =
    'h-8 rounded-full border border-white/10 bg-white/[0.04] px-2.5 text-[11px] font-semibold text-slate-200 hover:bg-white/[0.08] sm:h-9 sm:px-3';
  const removeRowButtonClassName =
    'h-7 w-7 justify-self-end self-end rounded-full border border-white/10 bg-white/[0.03] p-0 text-slate-300 hover:bg-rose-500/10 hover:text-rose-100 sm:h-8 sm:w-8';
  const { session, profile } = useAuth();
  const query = useSettingsQuery();
  const vdotQuery = useVdotQuery();

  const [ifZones, setIfZones] = useState({ z1_max: 0.7, z2_max: 0.8, z3_max: 0.9, z4_max: 1.0 });
  const [vdotLookbackDays, setVdotLookbackDays] = useState(200);
  const [specificity, setSpecificity] = useState<SpecificityProfile>({ non_running: 0.8, treadmill: 1.0, elliptical: 0.8, cycling: 0.8 });
  const [lthrRows, setLthrRows] = useState<LthrDraftRow[]>([]);
  const [paceRows, setPaceRows] = useState<LtPaceDraftRow[]>([]);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [showIfZonesGuide, setShowIfZonesGuide] = useState(true);

  useEffect(() => {
    if (!query.data) return;
    setIfZones(query.data.if_zone_thresholds);
    setVdotLookbackDays(Number(query.data.vdot_lookback_days) || 200);
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
    const bpm = (value: number) => `${value} bpm`;

    const rows = [
      {
        zone: 'Z1',
        ifRange: `< ${pct(z1)}%`,
        hrRange: `< ${bpm(hrAt(z1))}`,
        paceRange: `> ${formatPace(paceAt(z1))}`,
      },
      {
        zone: 'Z2',
        ifRange: `${pct(z1)}% - <${pct(z2)}%`,
        hrRange: `${bpm(hrAt(z1))} - ${bpm(hrAt(z2))}`,
        paceRange: `${formatPace(paceAt(z2))} - ${formatPace(paceAt(z1))}`,
      },
      {
        zone: 'Z3',
        ifRange: `${pct(z2)}% - <${pct(z3)}%`,
        hrRange: `${bpm(hrAt(z2))} - ${bpm(hrAt(z3))}`,
        paceRange: `${formatPace(paceAt(z3))} - ${formatPace(paceAt(z2))}`,
      },
      {
        zone: 'Z4',
        ifRange: `${pct(z3)}% - <${pct(z4)}%`,
        hrRange: `${bpm(hrAt(z3))} - ${bpm(hrAt(z4))}`,
        paceRange: `${formatPace(paceAt(z4))} - ${formatPace(paceAt(z3))}`,
      },
      {
        zone: 'Z5',
        ifRange: `>= ${pct(z4)}%`,
        hrRange: `> ${bpm(hrAt(z4))}`,
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

  return (
    <QueryShell isLoading={query.isLoading} isError={query.isError} error={query.error} errorTitle="Unable to load settings">
    <section className="space-y-4 sm:space-y-6">
      {saveMsg ? <p className="text-sm text-muted-foreground">{saveMsg}</p> : null}

      <SurfaceCard contentClassName="space-y-2.5 p-3 sm:space-y-3 sm:p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-medium">Temperance Guide</p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 rounded-full border-white/10 bg-white/[0.04] px-3 text-[11px] font-semibold text-slate-200 hover:bg-white/[0.08]"
              onClick={() => setShowIfZonesGuide((previous) => !previous)}
            >
              {showIfZonesGuide ? 'Hide guide' : 'Show guide'}
              <ChevronDown className={`ml-1.5 h-3.5 w-3.5 transition-transform ${showIfZonesGuide ? 'rotate-180' : ''}`} />
            </Button>
          </div>
          {showIfZonesGuide ? (
            <>
              <div className="grid gap-1.5 sm:hidden">
                {zoneGuide.rows.map((row) => (
                  <div key={row.zone} className="rounded-lg border border-white/10 bg-black/15 px-3 py-2">
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold">{row.zone}</p>
                      <p className="text-[11px] text-slate-300/72">{row.ifRange}</p>
                    </div>
                    <div className="grid gap-1 text-[11px] leading-4 text-slate-200/86">
                      <p>HR: {row.hrRange}</p>
                      <p>Pace: {row.paceRange}</p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="hidden overflow-x-auto rounded-xl border border-white/10 bg-black/15 sm:block">
                <table className="w-full text-sm">
                  <thead className="bg-white/5 text-left text-xs text-slate-300/72">
                    <tr>
                      <th className="px-3 py-2">Zone</th>
                      <th className="px-3 py-2">% LT</th>
                      <th className="px-3 py-2">HR Bands</th>
                      <th className="px-3 py-2">Pace Bands</th>
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
              {!vdotQuery.isLoading && !vdotQuery.isError && vdotQuery.data?.observed_max ? (
                <>
                  <div className="rounded-xl border border-sky-300/12 bg-[linear-gradient(180deg,rgba(14,26,40,0.92),rgba(3,7,18,0.96))] p-3 sm:hidden">
                    <div className="mb-3 flex items-start justify-between gap-3">
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">VDOT snapshot</p>
                        <p className="mt-1 text-xs text-slate-300/66">Current top effort and equivalent race paces.</p>
                      </div>
                      <div className="min-w-[72px] rounded-xl border border-sky-300/14 bg-sky-400/8 px-3 py-2 text-center">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-sky-200/74">VDOT Max</p>
                        <p className="mt-1 text-2xl font-semibold leading-none text-slate-50">{Math.round(vdotQuery.data.observed_max.vdot)}</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="rounded-lg border border-white/8 bg-black/15 px-3 py-2.5">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-300/58">Pred LT pace</p>
                        <p className="mt-1 text-sm font-semibold text-slate-50">{vdotQuery.data.observed_max.pred_lt_pace_label}</p>
                      </div>
                      <div className="rounded-lg border border-white/8 bg-black/15 px-3 py-2.5">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-300/58">10K</p>
                        <p className="mt-1 text-sm font-semibold text-slate-50">{vdotQuery.data.observed_max.equivalents['10k'].pace_label}</p>
                      </div>
                      <div className="rounded-lg border border-white/8 bg-black/15 px-3 py-2.5">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-300/58">HMP</p>
                        <p className="mt-1 text-sm font-semibold text-slate-50">{vdotQuery.data.observed_max.equivalents.half_marathon.pace_label}</p>
                      </div>
                      <div className="rounded-lg border border-white/8 bg-black/15 px-3 py-2.5">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-300/58">MP</p>
                        <p className="mt-1 text-sm font-semibold text-slate-50">{vdotQuery.data.observed_max.equivalents.marathon.pace_label}</p>
                      </div>
                    </div>
                    <div className="mt-2 rounded-lg border border-white/8 bg-black/15 px-3 py-2.5">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-300/58">Source Date</p>
                      <p className="mt-1 text-sm font-semibold text-slate-50">{vdotQuery.data.observed_max.source_date || '-'}</p>
                    </div>
                  </div>
                  <div className="hidden gap-2 sm:grid sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
                    <div className="rounded-xl border border-sky-300/12 bg-[linear-gradient(180deg,rgba(14,26,40,0.92),rgba(3,7,18,0.96))] px-3 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-200/74">VDOT Max</p>
                      <p className="mt-1 text-2xl font-semibold leading-none text-slate-50">{Math.round(vdotQuery.data.observed_max.vdot)}</p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-black/15 px-3 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-200/74">Pred LT pace</p>
                      <p className="mt-1 break-words text-base font-semibold text-slate-50 xl:text-lg">{vdotQuery.data.observed_max.pred_lt_pace_label}</p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-black/15 px-3 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-200/74">10K</p>
                      <p className="mt-1 break-words text-base font-semibold text-slate-50 xl:text-lg">{vdotQuery.data.observed_max.equivalents['10k'].pace_label}</p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-black/15 px-3 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-200/74">HMP</p>
                      <p className="mt-1 break-words text-base font-semibold text-slate-50 xl:text-lg">{vdotQuery.data.observed_max.equivalents.half_marathon.pace_label}</p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-black/15 px-3 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-200/74">MP</p>
                      <p className="mt-1 break-words text-base font-semibold text-slate-50 xl:text-lg">{vdotQuery.data.observed_max.equivalents.marathon.pace_label}</p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-black/15 px-3 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-200/74">Source Date</p>
                      <p className="mt-1 break-words text-base font-semibold text-slate-50 xl:text-lg">{vdotQuery.data.observed_max.source_date || '-'}</p>
                    </div>
                  </div>
                </>
              ) : null}
            </>
          ) : null}
      </SurfaceCard>

      <div className="grid gap-4 xl:grid-cols-2 xl:items-start">
        <SurfaceCard contentClassName="space-y-3 p-3 sm:space-y-4 sm:p-4">
            <p className="text-sm font-medium">Stress Zones and VDOT</p>
            <div className="grid gap-2 sm:gap-3 lg:grid-cols-5">
              {(['z1_max', 'z2_max', 'z3_max', 'z4_max'] as const).map((key) => (
                <div key={key} className="space-y-1 rounded-xl border border-white/8 bg-black/10 p-2.5 sm:rounded-none sm:border-0 sm:bg-transparent sm:p-0">
                  <FieldLabel htmlFor={`if-zone-${key}`}>{formatIfZoneLabel(key)}</FieldLabel>
                  <div className="relative">
                    <Input
                      id={`if-zone-${key}`}
                      type="number"
                      step="1"
                      className={`h-9 pr-14 sm:h-10 ${secondaryPageInputClassName}`}
                      value={Math.round((Number(ifZones[key]) || 0) * 100)}
                      onChange={(event) =>
                        setIfZones((previous) => ({
                          ...previous,
                          [key]: (Number(event.target.value) || 0) / 100,
                        }))
                      }
                    />
                    <span className="pointer-events-none absolute inset-y-0 right-3 inline-flex items-center text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-300/62">
                      % LT
                    </span>
                  </div>
                </div>
              ))}
              <div className="space-y-1 rounded-xl border border-white/8 bg-black/10 p-2.5 sm:rounded-none sm:border-0 sm:bg-transparent sm:p-0 lg:w-[96px] lg:justify-self-end">
                <FieldLabel htmlFor="vdot-lookback-days">VDOT Days</FieldLabel>
                <div className="relative">
                  <Input
                    id="vdot-lookback-days"
                    type="number"
                    min="1"
                    max="3650"
                    step="1"
                    className={`h-9 sm:h-10 ${secondaryPageInputClassName}`}
                    value={Math.round(Number(vdotLookbackDays) || 0)}
                    onChange={(event) => setVdotLookbackDays(Number(event.target.value) || 0)}
                  />
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="surface" className="w-full sm:w-auto"
                onClick={() => saveMutation.mutate({ if_zone_thresholds: ifZones, vdot_lookback_days: vdotLookbackDays })}
                disabled={saveMutation.isPending}
              >
                Save
              </Button>
            </div>
        </SurfaceCard>

        <SurfaceCard contentClassName="space-y-3 p-3 sm:space-y-4 sm:p-4">
            <p className="text-sm font-medium">Specificity Factors</p>
            <div className="grid gap-2 sm:gap-3 md:grid-cols-4">
              {(['non_running', 'treadmill', 'elliptical', 'cycling'] as const).map((key) => (
                <div key={key} className="space-y-1 rounded-xl border border-white/8 bg-black/10 p-2.5 sm:rounded-none sm:border-0 sm:bg-transparent sm:p-0">
                  <FieldLabel htmlFor={`specificity-${key}`}>{formatSpecificityLabel(key)}</FieldLabel>
                  <div className="relative">
                    <Input
                      id={`specificity-${key}`}
                      type="number"
                      step="1"
                      className={`h-9 pr-16 sm:h-10 ${secondaryPageInputClassName}`}
                      value={Math.round((Number(specificity[key]) || 0) * 100)}
                      onChange={(event) =>
                        setSpecificity((previous) => ({
                          ...previous,
                          [key]: (Number(event.target.value) || 0) / 100,
                        }))
                      }
                    />
                    <span className="pointer-events-none absolute inset-y-0 right-3 inline-flex items-center text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-300/62">
                      % TSS
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <Button variant="surface" className="w-full sm:w-auto" onClick={() => saveMutation.mutate({ specificity_profile: specificity })} disabled={saveMutation.isPending}>Save</Button>
        </SurfaceCard>
      </div>

      <div className="grid gap-4 xl:grid-cols-2 xl:items-start">
        <SurfaceCard contentClassName="space-y-3 p-3 sm:p-4">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium">LTHR Curve</p>
              <Button
                variant="outline"
                size="sm"
                className={addRowButtonClassName}
                onClick={() => setLthrRows((previous) => [...previous, { id: rowId(), date: '', lthr_bpm: 0 }])}
                disabled={saveMutation.isPending}
              >
                <Plus className="mr-1.5 h-3.5 w-3.5" />
                Add row
              </Button>
            </div>
            <div className="space-y-2">
              {lthrRows.map((row) => (
                <div key={row.id} className="grid gap-1.5 rounded-lg border border-white/8 bg-black/10 p-1.5 sm:items-end sm:gap-2 sm:rounded-none sm:border-0 sm:bg-transparent sm:p-0 md:grid-cols-[168px_132px_auto]">
                  <div className="space-y-0.5">
                    <p className={mobileCurveFieldLabelClassName}>Date</p>
                    <CompactDateInput
                      value={row.date}
                      onChange={(next) =>
                        setLthrRows((previous) => previous.map((item) => (item.id === row.id ? { ...item, date: next } : item)))
                      }
                      mobileInputClassName="h-8 rounded-md border-white/10 bg-black/10 px-2.5 text-[13px]"
                      desktopInputClassName="h-10 max-w-[168px]"
                    />
                  </div>
                  <div className="space-y-0.5">
                    <Label htmlFor={`lthr-bpm-${row.id}`} className={mobileCurveFieldLabelClassName}>LTHR</Label>
                    <Input
                      id={`lthr-bpm-${row.id}`}
                      className={`h-8 px-2.5 text-[13px] sm:h-10 sm:max-w-[132px] sm:px-3 sm:text-sm ${secondaryPageInputClassName}`}
                      type="number"
                      step="1"
                      min={0}
                      value={row.lthr_bpm}
                      onChange={(event) =>
                        setLthrRows((previous) => previous.map((item) => (item.id === row.id ? { ...item, lthr_bpm: Number(event.target.value) } : item)))
                      }
                      placeholder="LTHR bpm"
                    />
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className={removeRowButtonClassName}
                    onClick={() => setLthrRows((previous) => previous.filter((item) => item.id !== row.id))}
                    disabled={saveMutation.isPending}
                    aria-label="Remove LTHR row"
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </div>
            <Button variant="surface" className="w-full sm:w-auto" onClick={() => saveMutation.mutate({ lthr_curve: parsedCurves.lthr })} disabled={saveMutation.isPending}>Save</Button>
        </SurfaceCard>

        <SurfaceCard contentClassName="space-y-3 p-3 sm:p-4">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium">LT Pace Curve</p>
              <Button
                variant="outline"
                size="sm"
                className={addRowButtonClassName}
                onClick={() => setPaceRows((previous) => [...previous, { id: rowId(), date: '', pace_input: '' }])}
                disabled={saveMutation.isPending}
              >
                <Plus className="mr-1.5 h-3.5 w-3.5" />
                Add row
              </Button>
            </div>
            <div className="space-y-2">
              {paceRows.map((row) => (
                <div key={row.id} className="grid gap-1.5 rounded-lg border border-white/8 bg-black/10 p-1.5 sm:items-end sm:gap-2 sm:rounded-none sm:border-0 sm:bg-transparent sm:p-0 md:grid-cols-[168px_148px_auto]">
                  <div className="space-y-0.5">
                    <p className={mobileCurveFieldLabelClassName}>Date</p>
                    <CompactDateInput
                      value={row.date}
                      onChange={(next) =>
                        setPaceRows((previous) => previous.map((item) => (item.id === row.id ? { ...item, date: next } : item)))
                      }
                      mobileInputClassName="h-8 rounded-md border-white/10 bg-black/10 px-2.5 text-[13px]"
                      desktopInputClassName="h-10 max-w-[168px]"
                    />
                  </div>
                  <div className="space-y-0.5">
                    <Label htmlFor={`lt-pace-value-${row.id}`} className={mobileCurveFieldLabelClassName}>LT Pace</Label>
                    <Input
                      id={`lt-pace-value-${row.id}`}
                      className={`h-8 px-2.5 text-[13px] sm:h-10 sm:max-w-[148px] sm:px-3 sm:text-sm ${secondaryPageInputClassName}`}
                      type="text"
                      value={row.pace_input}
                      onChange={(event) =>
                        setPaceRows((previous) =>
                          previous.map((item) => (item.id === row.id ? { ...item, pace_input: event.target.value } : item)),
                        )
                      }
                      placeholder="e.g. 3:30 or 210"
                    />
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className={removeRowButtonClassName}
                    onClick={() => setPaceRows((previous) => previous.filter((item) => item.id !== row.id))}
                    disabled={saveMutation.isPending}
                    aria-label="Remove LT pace row"
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </div>
            {parsedCurves.paceError ? <p className="text-xs text-red-400">{parsedCurves.paceError}</p> : null}
            <Button
              variant="surface" className="w-full sm:w-auto"
              onClick={() => {
                if (parsedCurves.paceError) {
                  setSaveMsg(parsedCurves.paceError);
                  return;
                }
                saveMutation.mutate({ lt_pace_curve: parsedCurves.pace });
              }}
              disabled={saveMutation.isPending}
            >
              Save
            </Button>
        </SurfaceCard>
      </div>

    </section>
    </QueryShell>
  );
}
