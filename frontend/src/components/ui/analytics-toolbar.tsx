import { startTransition, useId } from 'react';

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  secondaryPageFieldLabelClassName,
  secondaryPageInputClassName,
  secondaryPageInsetClassName,
} from '@/components/ui/secondary-page';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { cn } from '@/lib/utils';

type AnalyticsAggregation = 'weekly' | 'daily';

interface CurrentPeriodControl {
  value: boolean;
  onValueChange: (value: boolean) => void;
  label?: string;
  includeLabel?: string;
  excludeLabel?: string;
  includeAriaLabel?: string;
  excludeAriaLabel?: string;
}

interface AnalyticsToolbarProps {
  days: number;
  onDaysChange: (days: number) => void;
  aggregation: AnalyticsAggregation;
  onAggregationChange: (value: AnalyticsAggregation) => void;
  currentPeriodControl?: CurrentPeriodControl;
  className?: string;
  compactLabels?: boolean;
}

interface SegmentedFieldProps {
  label: string;
  value: string;
  onValueChange: (value: string) => void;
  options: Array<{ value: string; label: string; ariaLabel?: string }>;
  compactLabel?: boolean;
}

const LOOKBACK_OPTIONS = [
  { value: '30', label: '1 month' },
  { value: '90', label: '3 months' },
  { value: '180', label: '6 months' },
  { value: '365', label: '1 year' },
  { value: '730', label: '2 years' },
  { value: '3000', label: 'All' },
] as const;

function FieldLabel({ id, children }: { id: string; children: string }): JSX.Element {
  return <p id={id} className={cn(secondaryPageFieldLabelClassName, 'text-[10px]')}>{children}</p>;
}

function SegmentedField({
  label,
  value,
  onValueChange,
  options,
  compactLabel = false,
}: SegmentedFieldProps): JSX.Element {
  const labelId = useId();

  return (
    <div className="grid gap-1.5">
      {compactLabel ? null : <FieldLabel id={labelId}>{label}</FieldLabel>}
      <ToggleGroup
        type="single"
        value={value}
        aria-label={compactLabel ? label : undefined}
        aria-labelledby={compactLabel ? undefined : labelId}
        className={cn(secondaryPageInsetClassName, 'w-full p-1 sm:w-auto')}
      >
        {options.map((option) => (
          <ToggleGroupItem
            key={option.value}
            value={option.value}
            aria-label={option.ariaLabel}
            size="sm"
            className="flex-1 sm:flex-none"
            onClick={() => startTransition(() => onValueChange(option.value))}
          >
            {option.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}

export function AnalyticsToolbar({
  days,
  onDaysChange,
  aggregation,
  onAggregationChange,
  currentPeriodControl,
  className,
  compactLabels = true,
}: AnalyticsToolbarProps): JSX.Element {
  const lookbackLabelId = useId();

  return (
    <div
      className={cn(
        'flex w-full flex-col gap-3 lg:w-auto lg:flex-row lg:flex-wrap lg:items-end lg:justify-end',
        className,
      )}
    >
      <div className={compactLabels ? 'lg:min-w-[9rem]' : 'grid gap-1.5 lg:min-w-[9rem]'}>
        {compactLabels ? null : <FieldLabel id={lookbackLabelId}>Lookback</FieldLabel>}
        <Select
          value={String(days)}
          onValueChange={(value) => {
            startTransition(() => onDaysChange(Number(value)));
          }}
        >
          <SelectTrigger
            aria-label="Lookback window"
            aria-labelledby={compactLabels ? undefined : lookbackLabelId}
            className={cn(secondaryPageInputClassName, 'w-full lg:w-[9rem]')}
          >
            <SelectValue placeholder="Lookback" />
          </SelectTrigger>
          <SelectContent>
            {LOOKBACK_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <SegmentedField
        label="Aggr"
        compactLabel={compactLabels}
        value={aggregation}
        onValueChange={(value) => onAggregationChange(value as AnalyticsAggregation)}
        options={[
          { value: 'weekly', label: 'W', ariaLabel: 'Weekly aggregation' },
          { value: 'daily', label: 'D', ariaLabel: 'Daily aggregation' },
        ]}
      />

      {currentPeriodControl ? (
        <SegmentedField
          label={currentPeriodControl.label ?? 'Period'}
          compactLabel={compactLabels}
          value={currentPeriodControl.value ? 'include' : 'exclude'}
          onValueChange={(value) => currentPeriodControl.onValueChange(value === 'include')}
          options={[
            {
              value: 'include',
              label: currentPeriodControl.includeLabel ?? 'Include',
              ariaLabel: currentPeriodControl.includeAriaLabel,
            },
            {
              value: 'exclude',
              label: currentPeriodControl.excludeLabel ?? 'Completed Only',
              ariaLabel: currentPeriodControl.excludeAriaLabel,
            },
          ]}
        />
      ) : null}
    </div>
  );
}
