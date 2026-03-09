import { Card, CardContent } from '@/components/ui/card';
import { DashboardDayColumn } from '@/features/dashboard/components/dashboard-day-column';
import { DashboardWeekSummaryCard } from '@/features/dashboard/components/dashboard-week-summary-card';
import type { DashboardWeekRow } from '@/features/dashboard/types/dashboard';

interface DashboardWeekCardProps {
  week: DashboardWeekRow;
  onAddPlannedActivity?: (dayUtc: string) => void;
  onMarkPlannedDone?: (activity: DashboardWeekRow['days'][number]['planned_activities'][number]) => void;
  onDeletePlannedActivity?: (activity: DashboardWeekRow['days'][number]['planned_activities'][number]) => void;
  onDeleteCustomActivity?: (activity: DashboardWeekRow['days'][number]['actual_activities'][number]) => void;
  onSelectActivity?: (activityId: string) => void;
  addingPlannedActivity?: boolean;
  markingPlannedDone?: boolean;
  deletingPlannedActivity?: boolean;
  deletingCustomActivity?: boolean;
  userTimeZone?: string;
}

function shortDay(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { day: '2-digit', month: 'short' });
}

export function DashboardWeekCard({
  week,
  onAddPlannedActivity,
  onMarkPlannedDone,
  onDeletePlannedActivity,
  onDeleteCustomActivity,
  onSelectActivity,
  addingPlannedActivity,
  markingPlannedDone,
  deletingPlannedActivity,
  deletingCustomActivity,
  userTimeZone,
}: DashboardWeekCardProps): JSX.Element {
  return (
    <div className="rounded-2xl bg-[linear-gradient(135deg,rgba(56,189,248,0.45),rgba(168,85,247,0.26),rgba(245,158,11,0.3))] p-[1px] shadow-[0_10px_30px_rgba(2,6,23,0.5)]">
      <Card className="overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_8%_10%,rgba(56,189,248,0.1),transparent_40%),radial-gradient(circle_at_88%_90%,rgba(168,85,247,0.11),transparent_45%)] shadow-inner">
        <CardContent className="p-1.5">
          <div className="grid gap-1.5 lg:grid-cols-[1.15fr_repeat(7,minmax(0,1fr))] lg:items-start">
            <DashboardWeekSummaryCard
              weekNumber={week.week_number}
              weekStart={shortDay(week.week_start)}
              weekEnd={shortDay(week.week_end)}
              summary={week.summary}
            />
            {week.days.map((day) => (
              <DashboardDayColumn
                key={day.day_utc}
                day={day}
                onAddPlannedActivity={onAddPlannedActivity}
                onMarkPlannedDone={onMarkPlannedDone}
                onDeletePlannedActivity={onDeletePlannedActivity}
                onDeleteCustomActivity={onDeleteCustomActivity}
                onSelectActivity={onSelectActivity}
                addingPlannedActivity={addingPlannedActivity}
                markingPlannedDone={markingPlannedDone}
                deletingPlannedActivity={deletingPlannedActivity}
                deletingCustomActivity={deletingCustomActivity}
                userTimeZone={userTimeZone}
              />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
