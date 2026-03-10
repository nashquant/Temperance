import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { WeeklyMetric } from '@/features/weekly-outlook/types/weekly-outlook';

interface MetricSelectorProps {
  value: WeeklyMetric;
  onValueChange: (metric: WeeklyMetric) => void;
}

export function MetricSelector({ value, onValueChange }: MetricSelectorProps): JSX.Element {
  return (
    <div className="grid w-full gap-1.5 sm:flex sm:w-auto sm:items-center sm:gap-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74 sm:text-sm sm:font-normal sm:tracking-normal sm:text-muted-foreground">
        Metric
      </p>
      <Select value={value} onValueChange={(next) => onValueChange(next as WeeklyMetric)}>
        <SelectTrigger className="w-full sm:w-[180px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="tss">TSS</SelectItem>
          <SelectItem value="rtss">rTSS</SelectItem>
          <SelectItem value="distance">Distance</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
