import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { WeeklyCompare } from '@/features/weekly-outlook/types/weekly-outlook';

interface CompareSelectorProps {
  value: WeeklyCompare;
  onValueChange: (compare: WeeklyCompare) => void;
}

export function CompareSelector({ value, onValueChange }: CompareSelectorProps): JSX.Element {
  return (
    <div className="grid w-full gap-1.5 sm:flex sm:w-auto sm:items-center sm:gap-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74 sm:text-sm sm:font-normal sm:tracking-normal sm:text-muted-foreground">
        Compare
      </p>
      <Select value={value} onValueChange={(next) => onValueChange(next as WeeklyCompare)}>
        <SelectTrigger className="w-full sm:w-[220px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="planned">Planned week</SelectItem>
          <SelectItem value="previous_week">Previous week</SelectItem>
          <SelectItem value="two_weeks_ago">Two weeks ago</SelectItem>
          <SelectItem value="three_weeks_ago">Three weeks ago</SelectItem>
          <SelectItem value="four_weeks_ago">Four weeks ago</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
