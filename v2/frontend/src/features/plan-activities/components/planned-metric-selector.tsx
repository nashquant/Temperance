import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
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
    <div
      className={
        compact
          ? 'w-auto'
          : 'grid w-full gap-2 rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.86),rgba(2,6,23,0.94))] p-3 sm:flex sm:w-auto sm:items-center sm:gap-3'
      }
    >
      {showLabel ? (
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74 sm:text-sm sm:font-normal sm:tracking-normal sm:text-muted-foreground">
          Planned Metric
        </p>
      ) : null}
      <ToggleGroup
        type="single"
        value={value}
        onValueChange={(next) => {
          if (next) onValueChange(next as PlannedMetricView);
        }}
        className={compact ? 'w-auto' : 'w-full sm:w-auto'}
      >
        {items.map((item) => (
          <ToggleGroupItem
            key={item.value}
            value={item.value}
            size="sm"
            className={compact ? 'h-7' : 'flex-1 sm:flex-none'}
          >
            {item.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
