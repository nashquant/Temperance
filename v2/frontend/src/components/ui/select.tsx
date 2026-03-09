import * as React from 'react';
import * as SelectPrimitive from '@radix-ui/react-select';
import { Check, ChevronDown } from 'lucide-react';

import { cn } from '@/lib/utils';

const Select = SelectPrimitive.Root;
const SelectValue = SelectPrimitive.Value;

const SelectTrigger = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Trigger
    ref={ref}
    className={cn(
      'flex h-10 w-full items-center justify-between rounded-xl border border-white/10 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.08),transparent_55%),linear-gradient(180deg,rgba(15,23,42,0.84),rgba(2,6,23,0.92))] px-3 py-2 text-sm text-slate-100 shadow-[0_10px_24px_rgba(2,6,23,0.18),inset_0_1px_0_rgba(255,255,255,0.04)] transition-colors focus:outline-none focus:ring-2 focus:ring-sky-300/25 disabled:cursor-not-allowed disabled:opacity-60',
      className,
    )}
    {...props}
  >
    {children}
    <SelectPrimitive.Icon asChild>
      <ChevronDown className="h-4 w-4 text-slate-300/70" />
    </SelectPrimitive.Icon>
  </SelectPrimitive.Trigger>
));
SelectTrigger.displayName = SelectPrimitive.Trigger.displayName;

const SelectContent = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Portal>
    <SelectPrimitive.Content
      ref={ref}
      className={cn(
        'z-50 min-w-[10rem] overflow-hidden rounded-2xl border border-white/10 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.96),rgba(2,6,23,0.98))] text-slate-100 shadow-[0_20px_40px_rgba(2,6,23,0.42)] backdrop-blur',
        className,
      )}
      {...props}
    >
      <SelectPrimitive.Viewport className="max-h-72 overflow-y-auto p-1.5">{children}</SelectPrimitive.Viewport>
    </SelectPrimitive.Content>
  </SelectPrimitive.Portal>
));
SelectContent.displayName = SelectPrimitive.Content.displayName;

const SelectItem = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Item
    ref={ref}
    className={cn(
      'relative flex w-full cursor-default select-none items-center rounded-xl py-2 pl-8 pr-3 text-sm text-slate-200/92 outline-none transition-colors focus:bg-white/10 focus:text-white data-[state=checked]:bg-sky-500/12 data-[state=checked]:text-sky-100',
      className,
    )}
    {...props}
  >
    <span className="absolute left-2.5 flex h-3.5 w-3.5 items-center justify-center">
      <SelectPrimitive.ItemIndicator>
        <Check className="h-4 w-4 text-sky-300" />
      </SelectPrimitive.ItemIndicator>
    </span>
    <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
  </SelectPrimitive.Item>
));
SelectItem.displayName = SelectPrimitive.Item.displayName;

export { Select, SelectContent, SelectItem, SelectTrigger, SelectValue };
