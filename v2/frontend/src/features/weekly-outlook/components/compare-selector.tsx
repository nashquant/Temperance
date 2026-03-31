import { secondaryPageFieldLabelClassName, secondaryPageInsetClassName } from '@/components/ui/secondary-page';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import type { WeeklyCompare } from '@/features/weekly-outlook/types/weekly-outlook';
import { cn } from '@/lib/utils';

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
    <div className="grid gap-1.5 sm:w-auto">
      <p className={cn(secondaryPageFieldLabelClassName, 'text-[10px]')}>Compare</p>
      <ToggleGroup
        type="single"
        value={value}
        onValueChange={(next) => {
          if (next) onValueChange(next as WeeklyCompare);
        }}
        className={cn(secondaryPageInsetClassName, 'w-full p-1 sm:w-auto')}
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
