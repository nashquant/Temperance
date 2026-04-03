import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';

interface MetricSelectorProps<T extends string> {
  value: T;
  onValueChange: (value: T) => void;
  items: Array<{ value: T; label: string }>;
  label?: string;
  showLabel?: boolean;
  compact?: boolean;
}

export function MetricSelector<T extends string>({
  value,
  onValueChange,
  items,
  label = 'Metric',
  showLabel = true,
  compact = false,
}: MetricSelectorProps<T>): JSX.Element {
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
          {label}
        </p>
      ) : null}
      <ToggleGroup
        type="single"
        value={value}
        onValueChange={(next) => {
          if (next) onValueChange(next as T);
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
