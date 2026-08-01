import Link from 'next/link';
import {
  Building2,
  Compass,
  Hammer,
  LayoutDashboard,
  MessagesSquare,
  Route,
  Trophy,
} from 'lucide-react';

import { SidebarNav } from '@/components/sidebar-nav';
import { ThemeToggle } from '@/components/theme-toggle';
import { UserBadgeStrip } from '@/components/user-menu';
import { getCurrentUser } from '@/lib/dal';

export const NAV_ITEMS = [
  { href: '/dashboard', label: 'Dashboard', icon: 'LayoutDashboard' },
  { href: '/roadmap', label: 'Your route', icon: 'Route' },
  { href: '/projects', label: 'Build', icon: 'Hammer' },
  { href: '/companies', label: 'Companies', icon: 'Building2' },
  { href: '/explore', label: 'Explore', icon: 'Compass' },
  { href: '/community', label: 'Community', icon: 'MessagesSquare' },
] as const;

export const NAV_ICONS = {
  LayoutDashboard,
  Route,
  Hammer,
  Building2,
  Compass,
  MessagesSquare,
  Trophy,
};

/**
 * The signed-in application frame: a fixed cartographic sidebar on large
 * screens, a compact drawer below that.
 *
 * The session is read here rather than in each page so the chrome renders
 * once, and pages stay focused on their own data.
 */
export async function AppShell({ children }: { children: React.ReactNode }) {
  const user = await getCurrentUser();

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-sidebar-border bg-sidebar lg:flex">
        <div className="border-b border-sidebar-border px-5 py-5">
          <Link href="/" className="group flex items-baseline gap-2">
            <span className="font-display text-xl leading-none font-semibold">
              Skill<span className="text-primary">Atlas</span>
            </span>
          </Link>
          <p className="eyebrow mt-2">Chart your route</p>
        </div>

        <SidebarNav className="flex-1 px-3 py-4" />

        <div className="space-y-3 border-t border-sidebar-border px-4 py-4">
          {user && <UserBadgeStrip user={user} />}
          <ThemeToggle className="w-full justify-center" />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col lg:pl-60">{children}</div>
    </div>
  );
}
