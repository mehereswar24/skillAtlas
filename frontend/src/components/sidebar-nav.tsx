'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Building2,
  Compass,
  Hammer,
  LayoutDashboard,
  MessagesSquare,
  Route,
} from 'lucide-react';

import { cn } from '@/lib/utils';

const ITEMS = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/roadmap', label: 'Your route', icon: Route },
  { href: '/projects', label: 'Build', icon: Hammer },
  { href: '/companies', label: 'Companies', icon: Building2 },
  { href: '/explore', label: 'Explore', icon: Compass },
  { href: '/community', label: 'Community', icon: MessagesSquare },
];

export function SidebarNav({ className }: { className?: string }) {
  const pathname = usePathname();

  return (
    <nav className={cn('space-y-0.5', className)} aria-label="Main">
      {ITEMS.map(({ href, label, icon: Icon }) => {
        // `/concepts/...` is part of the route the learner is following, so
        // "Your route" stays highlighted while reading a concept.
        const active =
          pathname === href ||
          pathname.startsWith(`${href}/`) ||
          (href === '/roadmap' && pathname.startsWith('/concepts'));

        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? 'page' : undefined}
            className={cn(
              'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
              active
                ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground',
            )}
          >
            <Icon className={cn('h-4 w-4', active && 'text-primary')} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

/** Horizontal version of the same nav, used in the mobile top bar. */
export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav
      className="flex gap-1 overflow-x-auto lg:hidden"
      aria-label="Main"
    >
      {ITEMS.map(({ href, label, icon: Icon }) => {
        const active =
          pathname === href ||
          pathname.startsWith(`${href}/`) ||
          (href === '/roadmap' && pathname.startsWith('/concepts'));

        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? 'page' : undefined}
            className={cn(
              'flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors',
              active
                ? 'bg-secondary text-foreground'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Icon className={cn('h-4 w-4', active && 'text-primary')} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
