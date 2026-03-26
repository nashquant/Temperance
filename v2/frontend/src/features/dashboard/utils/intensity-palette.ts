export const intensityHexPalette = {
  recovery: '#d7e4f2',
  easy: '#67b7ff',
  steady: '#d79a4a',
  threshold: '#ff7c78',
  vo2max: '#9a78ff',
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
