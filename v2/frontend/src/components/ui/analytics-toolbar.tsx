import { startTransition, useId } from 'react';

import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
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
  return (
    <p id={id} className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400/78">
      {children}
    </p>
  );
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
      <div
        role="group"
        aria-label={compactLabel ? label : undefined}
        aria-labelledby={compactLabel ? undefined : labelId}
        className="inline-flex w-full rounded-lg border border-white/10 bg-black/15 p-1 sm:w-auto"
      >
        {options.map((option) => (
          <Button
            key={option.value}
            type="button"
            variant={value === option.value ? 'secondary' : 'ghost'}
            size="sm"
            aria-pressed={value === option.value}
            aria-label={option.ariaLabel}
            className="h-8 flex-1 rounded-md px-2.5 text-xs sm:flex-none"
            onClick={() => {
              if (value === option.value) return;
              startTransition(() => onValueChange(option.value));
            }}
          >
            {option.label}
          </Button>
        ))}
      </div>
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
        'flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:flex-wrap sm:items-end sm:justify-end',
        className,
      )}
    >
      <div className={compactLabels ? 'sm:min-w-[9rem]' : 'grid gap-1.5 sm:min-w-[9rem]'}>
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
            className="w-full sm:w-[9rem]"
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
        label="Aggregation"
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
          label={currentPeriodControl.label ?? 'Current Period'}
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
