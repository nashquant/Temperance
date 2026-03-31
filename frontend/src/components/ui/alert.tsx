import * as React from 'react';

import { cn } from '@/lib/utils';

export function Alert({ className, ...props }: React.HTMLAttributes<HTMLDivElement>): JSX.Element {
  return <div role="alert" className={cn('relative w-full rounded-lg border px-4 py-3 text-sm', className)} {...props} />;
}

export function AlertTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>): JSX.Element {
  return <h5 className={cn('mb-1 font-medium', className)} {...props} />;
}

export function AlertDescription({ className, ...props }: React.HTMLAttributes<HTMLDivElement>): JSX.Element {
  return <div className={cn('text-sm text-muted-foreground', className)} {...props} />;
}
