import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { PlannedWeekSummary } from '@/features/plan-activities/types/plan-activities';

interface PlannedWeekSelectorProps {
  weeks: PlannedWeekSummary[];
  value: string;
  onValueChange: (weekStart: string) => void;
}

export function PlannedWeekSelector({ weeks, value, onValueChange }: PlannedWeekSelectorProps): JSX.Element {
  return (
    <div className="flex items-center gap-3">
      <p className="text-sm text-muted-foreground">Week</p>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger className="w-[220px]">
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
