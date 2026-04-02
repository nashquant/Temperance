export const intensityHexPalette = {
recovery:  '#9aa6b2', // neutral cool gray, softer and integrated
easy:      '#3b82f6', // controlled blue (less neon, more UI-native)
steady:    '#a1622a', // warmer, less muddy copper
threshold: '#d75959', // clean, balanced red (no brown, no neon)
vo2max:    '#6d5bd0', // slightly muted violet, more premium
} as const;

export function intensityHexFromKey(key: string): string {
  const normalized = String(key || '').trim().toLowerCase();
  if (normalized === 'green' || normalized === 'recovery') return intensityHexPalette.recovery;
  if (normalized === 'blue' || normalized === 'easy') return intensityHexPalette.easy;
  if (normalized === 'orange' || normalized === 'steady') return intensityHexPalette.steady;
  if (normalized === 'red' || normalized === 'threshold') return intensityHexPalette.threshold;
  if (normalized === 'purple' || normalized === 'vo2max' || normalized === 'vo2') return intensityHexPalette.vo2max;
  return intensityHexPalette.recovery;
}

export function intensityHexFromThreshold(thresholdBasis: number): string {
  if (thresholdBasis > 150) return intensityHexPalette.vo2max;
  if (thresholdBasis > 120) return intensityHexPalette.threshold;
  if (thresholdBasis > 80) return intensityHexPalette.steady;
  if (thresholdBasis > 50) return intensityHexPalette.easy;
  return intensityHexPalette.recovery;
}

export function zoneHexFromKey(key: string): string {
  return intensityHexFromKey(key);
}

export function zoneHexFromLabel(label: string): string {
  const normalized = String(label || '').trim().toUpperCase();
  if (normalized === 'Z1') return intensityHexPalette.recovery;
  if (normalized === 'Z2') return intensityHexPalette.easy;
  if (normalized === 'Z3') return intensityHexPalette.steady;
  if (normalized === 'Z4') return intensityHexPalette.threshold;
  if (normalized === 'Z5') return intensityHexPalette.vo2max;
  return intensityHexPalette.recovery;
}

/** Zone progress-bar track styling keyed by zone label (Z1–Z5). */
export const zoneTrackClassNames: Record<string, string> = {
  Z1: 'border-slate-500/30 bg-slate-500/8',
  Z2: 'border-sky-500/28 bg-sky-500/8',
  Z3: 'border-amber-500/28 bg-amber-500/8',
  Z4: 'border-rose-500/28 bg-rose-500/8',
  Z5: 'border-violet-500/28 bg-violet-500/8',
};

/** Default fallback for unknown zone labels. */
export const zoneTrackFallbackClassName = 'border-white/10 bg-white/5';
