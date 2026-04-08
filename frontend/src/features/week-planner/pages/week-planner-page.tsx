import { useState } from 'react';

import { Separator } from '@/components/ui/separator';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { PlanActivitiesSection } from '@/features/plan-activities/pages/plan-activities-page';
import { WeeklyOutlookSection } from '@/features/weekly-outlook/pages/weekly-outlook-page';

export function WeekPlannerPage(): JSX.Element {
  const [activeSection, setActiveSection] = useState<'plan' | 'outlook'>('plan');

  return (
    <section className="space-y-6">
      <div className="lg:hidden">
        <ToggleGroup
          type="single"
          value={activeSection}
          onValueChange={(next) => {
            if (next === 'plan' || next === 'outlook') setActiveSection(next);
          }}
          className="w-full"
        >
          <ToggleGroupItem value="plan" className="flex-1">
            Plan
          </ToggleGroupItem>
          <ToggleGroupItem value="outlook" className="flex-1">
            Outlook
          </ToggleGroupItem>
        </ToggleGroup>
      </div>

      <div className={activeSection === 'plan' ? 'block lg:block' : 'hidden lg:block'}>
        <PlanActivitiesSection embedded />
      </div>

      <Separator className="hidden lg:block" />

      <div className={activeSection === 'outlook' ? 'block lg:block' : 'hidden lg:block'}>
        <WeeklyOutlookSection embedded />
      </div>
    </section>
  );
}
