import Link from 'next/link';

import { ButtonLink } from '@/components/button-link';
import { MobileNav } from '@/components/sidebar-nav';
import { ThemeToggle } from '@/components/theme-toggle';
import { UserChip } from '@/components/user-menu';
import { getCurrentUser } from '@/lib/dal';

/**
 * Top bar.
 *
 * On large screens inside the app shell this is a thin context strip — the
 * sidebar carries navigation. On small screens it also carries the nav, since
 * the sidebar is hidden. On public pages it stands alone.
 */
export async function SiteHeader({
  variant = 'app',
}: {
  variant?: 'app' | 'marketing';
}) {
  return null;
}
