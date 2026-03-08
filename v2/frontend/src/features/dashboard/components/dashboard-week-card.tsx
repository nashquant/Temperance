import { DashboardDayColumn } from '@/features/dashboard/components/dashboard-day-column';
import { DashboardWeekSummaryCard } from '@/features/dashboard/components/dashboard-week-summary-card';
import type { DashboardWeekRow } from '@/features/dashboard/types/dashboard';

interface DashboardWeekCardProps {
  week: DashboardWeekRow;
}

function shortDay(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { day: '2-digit', month: 'short' });
}

export function DashboardWeekCard({ week }: DashboardWeekCardProps): JSX.Element {
  return (
    <section className="rounded-2xl border border-border/70 bg-card/40 p-3">
      <div className="grid gap-2 lg:grid-cols-[1.2fr_repeat(7,minmax(0,1fr))]">
        <DashboardWeekSummaryCard
          weekNumber={week.week_number}
          weekStart={shortDay(week.week_start)}
          weekEnd={shortDay(week.week_end)}
          summary={week.summary}
        />
        {week.days.map((day) => (
          <DashboardDayColumn key={day.day_utc} day={day} />
        ))}
      </div>
    </section>
  );
}
