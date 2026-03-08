import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { WeeklyMetric } from '@/features/weekly-outlook/types/weekly-outlook';

interface MetricSelectorProps {
  value: WeeklyMetric;
  onValueChange: (metric: WeeklyMetric) => void;
}

export function MetricSelector({ value, onValueChange }: MetricSelectorProps): JSX.Element {
  return (
    <div className="flex items-center gap-3">
      <p className="text-sm text-muted-foreground">Metric</p>
      <Select value={value} onValueChange={(next) => onValueChange(next as WeeklyMetric)}>
        <SelectTrigger className="w-[180px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="tss">TSS</SelectItem>
          <SelectItem value="distance">Distance</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
