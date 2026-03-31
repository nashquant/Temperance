import { Separator } from '@/components/ui/separator';
import { SecondaryPageHeader } from '@/components/ui/secondary-page';
import { PlanActivitiesSection } from '@/features/plan-activities/pages/plan-activities-page';
import { WeeklyOutlookSection } from '@/features/weekly-outlook/pages/weekly-outlook-page';

export function WeekPlannerPage(): JSX.Element {
  return (
    <section className="space-y-6">
      <SecondaryPageHeader
        title="Week Planner"
        description="Plan the week ahead, then compare how the structure is tracking against the target."
      />

      <PlanActivitiesSection embedded />

      <Separator />

      <WeeklyOutlookSection embedded />
    </section>
  );
}
