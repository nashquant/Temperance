import type * as React from 'react';

import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export const secondaryPageSurfaceClassName =
  'overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]';

export const secondaryPageInsetClassName =
  'rounded-xl border border-white/10 bg-black/15';

export const secondaryPageMutedInsetClassName =
  'rounded-xl border border-white/8 bg-white/[0.03]';

export const secondaryPageActionButtonClassName =
  'h-9 rounded-xl border border-white/10 bg-[linear-gradient(180deg,rgba(30,41,59,0.88),rgba(15,23,42,0.96))] px-3 text-[12px] font-medium text-slate-100 shadow-[0_8px_18px_rgba(2,6,23,0.22)] hover:border-white/16 hover:bg-[linear-gradient(180deg,rgba(51,65,85,0.92),rgba(15,23,42,0.98))] sm:h-10 sm:px-4';

export const secondaryPageFieldLabelClassName =
  'text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74';

export const secondaryPageInputClassName =
  'border-white/10 bg-black/15 text-foreground focus:border-sky-300/40 focus:ring-2 focus:ring-sky-300/20';

export const secondaryPageTextAreaClassName =
  'w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2.5 text-sm text-foreground outline-none transition focus:border-sky-300/40 focus:ring-2 focus:ring-sky-300/20 sm:py-3';

interface SecondaryStatCardProps {
  label: string;
  value: React.ReactNode;
  meta?: React.ReactNode;
  className?: string;
}

export function SecondaryStatCard({
  label,
  value,
  meta,
  className,
}: SecondaryStatCardProps): JSX.Element {
  return (
    <div className={cn(secondaryPageMutedInsetClassName, 'relative p-3.5', className)}>
      <div className="pointer-events-none absolute inset-x-3.5 top-0 h-px bg-gradient-to-r from-transparent via-sky-200/24 to-transparent" />
      <div className="flex h-full min-h-[92px] flex-col justify-between gap-4">
        <div className="space-y-1.5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">{label}</p>
          {meta ? <p className="text-xs leading-5 text-slate-300/68">{meta}</p> : null}
        </div>
        <div className="flex items-end justify-between gap-3">
          <div className="h-1.5 w-10 rounded-full bg-gradient-to-r from-sky-300/50 to-transparent" />
          <div className="text-right text-2xl font-semibold tracking-[-0.03em] text-slate-50">{value}</div>
        </div>
      </div>
    </div>
  );
}

interface SecondaryPageHeaderProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}

export function SecondaryPageHeader({
  title,
  description,
  actions,
}: SecondaryPageHeaderProps): JSX.Element {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
      <div className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {actions ? <div className="flex w-full flex-col gap-3 md:w-auto md:items-end">{actions}</div> : null}
    </div>
  );
}

interface SecondaryPageSectionCardProps {
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
}

export function SecondaryPageSectionCard({
  children,
  className,
  contentClassName,
}: SecondaryPageSectionCardProps): JSX.Element {
  return (
    <Card className={cn(secondaryPageSurfaceClassName, className)}>
      <CardContent className={cn('p-4 sm:p-5', contentClassName)}>{children}</CardContent>
    </Card>
  );
}
