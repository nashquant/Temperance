import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { PlannedWeekSummary } from '@/features/plan-activities/types/plan-activities';

interface PlannedWeekSelectorProps {
  weeks: PlannedWeekSummary[];
  value: string;
  onValueChange: (weekStart: string) => void;
}

export function PlannedWeekSelector({ weeks, value, onValueChange }: PlannedWeekSelectorProps): JSX.Element {
  return (
    <div className="grid w-full gap-1.5 sm:flex sm:w-auto sm:items-center sm:gap-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74 sm:text-sm sm:font-normal sm:tracking-normal sm:text-muted-foreground">
        Week
      </p>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger className="w-full sm:w-[220px]">
          <SelectValue placeholder="Select week" />
        </SelectTrigger>
        <SelectContent>
          {weeks.map((week) => (
            <SelectItem key={week.week_start} value={week.week_start}>
              {week.week_label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
