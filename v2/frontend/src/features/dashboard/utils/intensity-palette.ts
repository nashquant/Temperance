export const intensityHexPalette = {
recovery:  '#bcd4ec',  // cooler, still soft but less washed
easy:      '#3ea0ff',  // more saturated blue, clearer identity
steady:    '#c46a1f',  // richer copper, less muddy
threshold: '#ff5a52',  // sharper red, more urgency
vo2max:    '#7a5cff',  // deeper violet, more punch
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
