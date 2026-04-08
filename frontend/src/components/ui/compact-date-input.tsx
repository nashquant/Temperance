import { useEffect, useState } from 'react';
import { CalendarDays } from 'lucide-react';

import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { normalizeCompactDateInput } from '@/lib/date-input';

interface CompactDateInputProps {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  mobileInputClassName?: string;
  tabletInputClassName?: string;
  desktopInputClassName?: string;
  buttonClassName?: string;
  tabletButtonClassName?: string;
  useTabletCompactVariant?: boolean;
  desktopBreakpoint?: 'sm' | 'lg' | 'xl';
}

export function CompactDateInput({
  value,
  onChange,
  placeholder = 'YYYY-MM-DD',
  mobileInputClassName,
  tabletInputClassName,
  desktopInputClassName,
  buttonClassName,
  tabletButtonClassName,
  useTabletCompactVariant = false,
  desktopBreakpoint = 'sm',
}: CompactDateInputProps): JSX.Element {
  const [draftValue, setDraftValue] = useState(value);

  useEffect(() => {
    setDraftValue(value);
  }, [value]);

  const normalizedValue = normalizeCompactDateInput(value) ?? '';
  const normalizeAndCommit = (): void => {
    const normalized = normalizeCompactDateInput(draftValue);
    if (normalized) {
      setDraftValue(normalized);
      if (normalized !== value) {
        onChange(normalized);
      }
      return;
    }
    const trimmed = draftValue.trim();
    setDraftValue(trimmed);
    if (trimmed !== value) {
      onChange(trimmed);
    }
  };

  const compactVisibilityClassName = useTabletCompactVariant
    ? desktopBreakpoint === 'xl'
      ? 'xl:hidden'
      : 'lg:hidden'
    : 'sm:hidden';
  const desktopVisibilityClassName = useTabletCompactVariant
    ? desktopBreakpoint === 'xl'
      ? 'xl:block'
      : 'lg:block'
    : 'sm:block';

  return (
    <>
      <div className={cn('flex items-center gap-1.5', compactVisibilityClassName)}>
        <Input
          type="text"
          inputMode="text"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          value={draftValue}
          onChange={(event) => setDraftValue(event.target.value)}
          onBlur={normalizeAndCommit}
          placeholder={placeholder}
          className={cn(
            'h-8 rounded-md border-white/10 bg-black/10 px-2.5 text-[13px]',
            useTabletCompactVariant ? 'sm:h-10 sm:rounded-xl sm:px-3.5 sm:text-sm' : null,
            mobileInputClassName,
            useTabletCompactVariant ? tabletInputClassName : null,
          )}
        />
        <label
          className={cn(
            'relative inline-flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center overflow-hidden rounded-md border border-input bg-background text-foreground shadow-sm',
            buttonClassName,
            useTabletCompactVariant ? 'sm:h-10 sm:w-10 sm:rounded-xl' : null,
            useTabletCompactVariant ? tabletButtonClassName : null,
          )}
          aria-label="Open date picker"
        >
          <CalendarDays className="pointer-events-none h-3.5 w-3.5" />
          <input
            type="date"
            value={normalizedValue}
            onChange={(event) => {
              setDraftValue(event.target.value);
              onChange(event.target.value);
            }}
            className="absolute inset-0 z-0 h-full min-h-0 w-full min-w-0 cursor-pointer appearance-none opacity-0"
            aria-label="Select date"
          />
        </label>
      </div>
      <Input
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={cn('hidden h-10', desktopVisibilityClassName, desktopInputClassName)}
      />
    </>
  );
}
