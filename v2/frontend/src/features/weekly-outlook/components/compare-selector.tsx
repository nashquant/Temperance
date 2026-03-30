import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import type { WeeklyCompare } from '@/features/weekly-outlook/types/weekly-outlook';

interface CompareSelectorProps {
  value: WeeklyCompare;
  onValueChange: (compare: WeeklyCompare) => void;
}

export function CompareSelector({ value, onValueChange }: CompareSelectorProps): JSX.Element {
  const items: Array<{ value: WeeklyCompare; label: string }> = [
    { value: 'planned', label: 'Planned' },
    { value: 'previous_week', label: 'Previous' },
  ];

  return (
    <div className="grid w-full gap-2 rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.86),rgba(2,6,23,0.94))] p-3 sm:flex sm:w-auto sm:items-center sm:gap-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74 sm:text-sm sm:font-normal sm:tracking-normal sm:text-muted-foreground">
        Compare
      </p>
      <ToggleGroup
        type="single"
        value={value}
        onValueChange={(next) => {
          if (next) onValueChange(next as WeeklyCompare);
        }}
        className="w-full sm:w-auto"
      >
        {items.map((item) => (
          <ToggleGroupItem
            key={item.value}
            value={item.value}
            size="sm"
            className="flex-1 sm:flex-none"
          >
            {item.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
