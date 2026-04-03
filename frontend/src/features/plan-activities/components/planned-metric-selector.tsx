import { MetricSelector } from '@/components/ui/metric-selector';
import type { PlannedMetricView } from '@/features/plan-activities/types/plan-activities';

const ITEMS: Array<{ value: PlannedMetricView; label: string }> = [
  { value: 'tss', label: 'TSS' },
  { value: 'rtss', label: 'rTSS' },
  { value: 'distance_eqv_km', label: 'Distance' },
];

interface PlannedMetricSelectorProps {
  value: PlannedMetricView;
  onValueChange: (value: PlannedMetricView) => void;
  showLabel?: boolean;
  compact?: boolean;
}

export function PlannedMetricSelector(props: PlannedMetricSelectorProps): JSX.Element {
  return <MetricSelector {...props} label="Planned Metric" items={ITEMS} />;
}
