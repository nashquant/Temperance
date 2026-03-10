import { Button } from '@/components/ui/button';
import type { PlannedMetricView } from '@/features/plan-activities/types/plan-activities';

interface PlannedMetricSelectorProps {
  value: PlannedMetricView;
  onValueChange: (value: PlannedMetricView) => void;
  showLabel?: boolean;
  compact?: boolean;
}

export function PlannedMetricSelector({
  value,
  onValueChange,
  showLabel = true,
  compact = false,
}: PlannedMetricSelectorProps): JSX.Element {
  const items: Array<{ value: PlannedMetricView; label: string }> = [
    { value: 'tss', label: 'TSS' },
    { value: 'rtss', label: 'rTSS' },
    { value: 'distance_eqv_km', label: 'Distance' },
  ];

  return (
    <div className={`${compact ? 'w-auto' : 'grid w-full gap-1.5 sm:flex sm:w-auto sm:items-center sm:gap-3'}`}>
      {showLabel ? (
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74 sm:text-sm sm:font-normal sm:tracking-normal sm:text-muted-foreground">
          Planned Metric
        </p>
      ) : null}
      <div className={`inline-flex rounded-lg border border-white/10 bg-black/15 p-1 ${compact ? 'w-auto' : 'w-full sm:w-auto'}`}>
        {items.map((item) => (
          <Button
            key={item.value}
            variant={value === item.value ? 'secondary' : 'ghost'}
            size="sm"
            className={`rounded-md px-2.5 text-xs ${compact ? 'h-7' : 'h-8 flex-1 sm:flex-none'}`}
            onClick={() => onValueChange(item.value)}
          >
            {item.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
