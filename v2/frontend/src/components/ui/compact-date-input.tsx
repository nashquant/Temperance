import { useRef } from 'react';
import { CalendarDays } from 'lucide-react';

import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface CompactDateInputProps {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  mobileInputClassName?: string;
  desktopInputClassName?: string;
  buttonClassName?: string;
}

export function CompactDateInput({
  value,
  onChange,
  placeholder = 'YYYY-MM-DD',
  mobileInputClassName,
  desktopInputClassName,
  buttonClassName,
}: CompactDateInputProps): JSX.Element {
  const pickerRef = useRef<HTMLInputElement | null>(null);

  const openPicker = () => {
    const input = pickerRef.current as (HTMLInputElement & { showPicker?: () => void }) | null;
    if (!input) return;
    if (typeof input.showPicker === 'function') {
      input.showPicker();
      return;
    }
    input.focus();
    input.click();
  };

  return (
    <>
      <div className="flex items-center gap-1.5 sm:hidden">
        <Input
          type="text"
          inputMode="numeric"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          className={cn('h-8 rounded-md border-white/10 bg-black/10 px-2.5 text-[13px]', mobileInputClassName)}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          className={cn('h-8 w-8 shrink-0 px-0', buttonClassName)}
          onClick={openPicker}
          aria-label="Open date picker"
        >
          <CalendarDays className="h-3.5 w-3.5" />
        </Button>
        <input
          ref={pickerRef}
          type="date"
          tabIndex={-1}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="sr-only"
          aria-hidden="true"
        />
      </div>
      <Input
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={cn('hidden h-10 sm:block', desktopInputClassName)}
      />
    </>
  );
}
