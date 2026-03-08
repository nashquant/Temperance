import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { WeeklyCompare } from '@/features/weekly-outlook/types/weekly-outlook';

interface CompareSelectorProps {
  value: WeeklyCompare;
  onValueChange: (compare: WeeklyCompare) => void;
}

export function CompareSelector({ value, onValueChange }: CompareSelectorProps): JSX.Element {
  return (
    <div className="flex items-center gap-3">
      <p className="text-sm text-muted-foreground">Compare</p>
      <Select value={value} onValueChange={(next) => onValueChange(next as WeeklyCompare)}>
        <SelectTrigger className="w-[220px]">
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
