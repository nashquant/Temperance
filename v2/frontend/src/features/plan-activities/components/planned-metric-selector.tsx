import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { PlannedMetricView } from '@/features/plan-activities/types/plan-activities';

interface PlannedMetricSelectorProps {
  value: PlannedMetricView;
  onValueChange: (value: PlannedMetricView) => void;
}

export function PlannedMetricSelector({ value, onValueChange }: PlannedMetricSelectorProps): JSX.Element {
  return (
    <div className="grid w-full gap-1.5 sm:flex sm:w-auto sm:items-center sm:gap-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74 sm:text-sm sm:font-normal sm:tracking-normal sm:text-muted-foreground">
        Planned Metric
      </p>
      <Select value={value} onValueChange={(next) => onValueChange(next as PlannedMetricView)}>
        <SelectTrigger className="w-full sm:w-[180px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="tss">TSS</SelectItem>
          <SelectItem value="rtss">rTSS</SelectItem>
          <SelectItem value="distance_eqv_km">Dist Eqv (km)</SelectItem>
          <SelectItem value="if_proxy_pct">IF</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
