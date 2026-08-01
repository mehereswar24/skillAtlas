import Link from 'next/link';
import type { VariantProps } from 'class-variance-authority';

import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/**
 * A link styled as a button.
 *
 * Base UI's `Button` can render an anchor via its `render` prop, but that also
 * needs `nativeButton={false}` every time to stay accessible. Styling the link
 * directly is simpler and impossible to get wrong.
 */
export function ButtonLink({
  className,
  variant,
  size,
  ...props
}: React.ComponentProps<typeof Link> & VariantProps<typeof buttonVariants>) {
  return <Link data-magnetic className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}
