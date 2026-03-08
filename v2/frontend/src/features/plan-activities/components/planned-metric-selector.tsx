import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { PlannedMetricView } from '@/features/plan-activities/types/plan-activities';

interface PlannedMetricSelectorProps {
  value: PlannedMetricView;
  onValueChange: (value: PlannedMetricView) => void;
}

export function PlannedMetricSelector({ value, onValueChange }: PlannedMetricSelectorProps): JSX.Element {
  return (
    <div className="flex items-center gap-3">
      <p className="text-sm text-muted-foreground">Planned metric</p>
      <Select value={value} onValueChange={(next) => onValueChange(next as PlannedMetricView)}>
        <SelectTrigger className="w-[180px]">
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
