import type * as React from 'react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { secondaryPageSurfaceClassName } from '@/components/ui/secondary-page';
import { cn } from '@/lib/utils';

interface ChartCardProps {
  /** Optional title displayed in a compact CardHeader. */
  title?: string;
  /** Controls or selectors rendered above the chart area. */
  toolbar?: React.ReactNode;
  /** Height class for the chart container, e.g. "h-[280px]". */
  heightClassName?: string;
  /** Additional className on the outer Card. */
  className?: string;
  children: React.ReactNode;
}

/**
 * Standard card shell for Recharts-based visualisations.
 *
 * Provides the surface gradient, optional title / toolbar, and a
 * height-constrained container for `<ResponsiveContainer>`.
 */
export function ChartCard({
  title,
  toolbar,
  heightClassName,
  className,
  children,
}: ChartCardProps): JSX.Element {
  return (
    <Card className={cn(secondaryPageSurfaceClassName, className)}>
      {title ? (
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-slate-200/88">{title}</CardTitle>
        </CardHeader>
      ) : null}
      <CardContent className={cn(title ? 'p-4 pt-0' : 'px-4 pb-4 pt-5')}>
        {toolbar ? <div className="mb-3 flex items-start justify-between gap-3">{toolbar}</div> : null}
        {heightClassName
          ? <div className={cn(heightClassName, 'w-full')}>{children}</div>
          : children}
      </CardContent>
    </Card>
  );
}
