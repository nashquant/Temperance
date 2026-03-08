import { Separator } from '@/components/ui/separator';
import { PlanActivitiesSection } from '@/features/plan-activities/pages/plan-activities-page';
import { WeeklyOutlookSection } from '@/features/weekly-outlook/pages/weekly-outlook-page';

export function WeekPlannerPage(): JSX.Element {
  return (
    <section className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Week Planner</h1>
        <p className="mt-1 text-sm text-muted-foreground">Weekly outlook plus planned activities in one place.</p>
      </div>

      <WeeklyOutlookSection embedded />

      <Separator />

      <PlanActivitiesSection embedded />
    </section>
  );
}
