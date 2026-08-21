'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Briefcase,
  Building2,
  Compass,
  FileText,
  Hammer,
  LayoutDashboard,
  MessagesSquare,
  Mic,
  Route,
  UserSquare,
} from 'lucide-react';

import { cn } from '@/lib/utils';

const ITEMS = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/roadmap', label: 'Your route', icon: Route },
  { href: '/projects', label: 'Build', icon: Hammer },
  { href: '/companies', label: 'Companies', icon: Building2 },
  { href: '/explore', label: 'Explore', icon: Compass },
  // Career features. Listed up front so parallel work on each never contends
  // on this file.
  { href: '/resume', label: 'Résumé', icon: FileText },
  { href: '/interviews', label: 'Mock interview', icon: Mic },
  { href: '/applications', label: 'Applications', icon: Briefcase },
  { href: '/portfolio', label: 'Portfolio', icon: UserSquare },
  { href: '/community', label: 'Community', icon: MessagesSquare },
];

import {
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
} from '@/components/lightswind/sidebar';

export function SidebarNav({ className }: { className?: string }) {
  const pathname = usePathname();

  return (
    <SidebarMenu className={className} aria-label="Main">
      {ITEMS.map(({ href, label, icon: Icon }) => {
        // `/concepts/...` is part of the route the learner is following, so
        // "Your route" stays highlighted while reading a concept.
        const active =
          pathname === href ||
          pathname.startsWith(`${href}/`) ||
          (href === '/roadmap' && pathname.startsWith('/concepts'));

        return (
          <SidebarMenuItem key={href} value={href}>
            <SidebarMenuButton asChild isActive={active}>
              <Link href={href}>
                <Icon className={cn('h-4 w-4', active && 'text-primarylw')} />
                <span>{label}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        );
      })}
    </SidebarMenu>
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
