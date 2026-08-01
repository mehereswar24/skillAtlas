'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Flame, LogOut } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { User } from '@/lib/types';

function initials(user: User): string {
  const source = user.display_name?.trim() || user.email;
  return source
    .split(/[\s._-]+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join('');
}

function levelPercent(user: User): number {
  const { xp_into_level, xp_for_next_level } = user.profile;
  return xp_for_next_level ? Math.round((xp_into_level / xp_for_next_level) * 100) : 0;
}

/**
 * Sidebar footer: who you are, how far into the current level, and the
 * streak. Every number comes from the API — there is no placeholder path.
 */
export function UserBadgeStrip({ user }: { user: User }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const { profile } = user;

  async function logout() {
    setPending(true);
    await fetch('/api/auth/logout', { method: 'POST' });
    router.push('/');
    router.refresh();
  }

  return (
    <div className="rounded-lg border bg-card p-3">
      <div className="flex items-center gap-2.5">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary text-xs font-semibold text-primary-foreground">
          {initials(user)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">
            {user.display_name ?? user.email}
          </span>
          <span className="block text-xs text-muted-foreground">
            Level {profile.level}
            {profile.streak_days > 0 && (
              <>
                {' · '}
                <span className="inline-flex items-baseline gap-0.5 text-primary">
                  <Flame className="inline h-3 w-3" />
                  {profile.streak_days}
                </span>
              </>
            )}
          </span>
        </span>
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={logout}
          disabled={pending}
          aria-label="Sign out"
          title="Sign out"
        >
          <LogOut />
        </Button>
      </div>

      <div className="mt-3">
        <div
          className="h-1 w-full overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={levelPercent(user)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Progress to level ${profile.level + 1}`}
        >
          <div
            className="h-full bg-primary transition-all"
            style={{ width: `${levelPercent(user)}%` }}
          />
        </div>
        <p className="mt-1.5 text-[11px] text-muted-foreground tabular-nums">
          {profile.xp_into_level} / {profile.xp_for_next_level} XP to level{' '}
          {profile.level + 1}
        </p>
      </div>
    </div>
  );
}

/** Compact inline version for the mobile top bar. */
export function UserChip({ user, className }: { user: User; className?: string }) {
  const { profile } = user;

  return (
    <Link
      href="/dashboard"
      className={cn('flex items-center gap-2 rounded-md px-2 py-1 hover:bg-muted', className)}
      title={`${profile.xp.toLocaleString()} XP`}
    >
      <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-[11px] font-semibold text-primary-foreground">
        {initials(user)}
      </span>
      <span className="hidden text-xs leading-tight sm:block">
        <span className="block font-medium">Level {profile.level}</span>
        {profile.streak_days > 0 && (
          <span className="flex items-center gap-0.5 text-primary">
            <Flame className="h-3 w-3" />
            {profile.streak_days}
          </span>
        )}
      </span>
    </Link>
  );
}
