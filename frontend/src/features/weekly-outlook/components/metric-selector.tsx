import { MetricSelector as BaseMetricSelector } from '@/components/ui/metric-selector';
import type { WeeklyMetric } from '@/features/weekly-outlook/types/weekly-outlook';

const ITEMS: Array<{ value: WeeklyMetric; label: string }> = [
  { value: 'tss', label: 'TSS' },
  { value: 'rtss', label: 'rTSS' },
  { value: 'distance', label: 'Distance' },
];

interface MetricSelectorProps {
  value: WeeklyMetric;
  onValueChange: (metric: WeeklyMetric) => void;
  showLabel?: boolean;
  compact?: boolean;
}

export function MetricSelector(props: MetricSelectorProps): JSX.Element {
  return <BaseMetricSelector {...props} items={ITEMS} />;
}
