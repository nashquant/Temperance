import { Button } from '@/components/ui/button';
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
    <div className="grid w-full gap-1.5 sm:flex sm:w-auto sm:items-center sm:gap-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74 sm:text-sm sm:font-normal sm:tracking-normal sm:text-muted-foreground">
        Compare
      </p>
      <div className="inline-flex w-full rounded-lg border border-white/10 bg-black/15 p-1 sm:w-auto">
        {items.map((item) => (
          <Button
            key={item.value}
            variant={value === item.value ? 'secondary' : 'ghost'}
            size="sm"
            className="h-8 flex-1 rounded-md px-2.5 text-xs sm:flex-none"
            onClick={() => onValueChange(item.value)}
          >
            {item.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
