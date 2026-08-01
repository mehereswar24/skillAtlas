'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import * as Icons from 'lucide-react';
import { ArrowRight, Search } from 'lucide-react';

import { cn } from '@/lib/utils';
import type { Domain, TrackSummary } from '@/lib/types';

/** Resolve the lucide icon name stored on the domain row. */
function DomainIcon({ name, className }: { name: string; className?: string }) {
  const Icon = (Icons as unknown as Record<string, typeof Icons.BookOpen>)[name];
  const Resolved = Icon ?? Icons.BookOpen;
  return <Resolved className={className} />;
}

export function DomainExplorer({
  domains,
  tracks,
  categories,
}: {
  domains: Domain[];
  tracks: TrackSummary[];
  categories: string[];
}) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<string | null>(null);

  const tracksByDomain = useMemo(() => {
    const map = new Map<string, TrackSummary[]>();
    for (const track of tracks) {
      map.set(track.domain_slug, [...(map.get(track.domain_slug) ?? []), track]);
    }
    return map;
  }, [tracks]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return domains.filter((domain) => {
      if (category && domain.category !== category) return false;
      if (!needle) return true;
      return (
        domain.name.toLowerCase().includes(needle) ||
        (domain.description ?? '').toLowerCase().includes(needle) ||
        (tracksByDomain.get(domain.slug) ?? []).some((t) =>
          t.title.toLowerCase().includes(needle),
        )
      );
    });
  }, [domains, query, category, tracksByDomain]);

  // Group by category so the atlas reads as an index rather than a wall.
  const grouped = useMemo(() => {
    const map = new Map<string, Domain[]>();
    for (const domain of filtered) {
      map.set(domain.category, [...(map.get(domain.category) ?? []), domain]);
    }
    return [...map.entries()];
  }, [filtered]);

  return (
    <>
      <div className="mb-10 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="relative lg:w-80">
          <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search domains and routes…"
            aria-label="Search domains"
            className="w-full rounded-md border bg-card py-2 pr-3 pl-9 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>

        <div className="flex flex-wrap gap-1.5">
          <FilterChip active={category === null} onClick={() => setCategory(null)}>
            All
          </FilterChip>
          {categories.map((name) => (
            <FilterChip
              key={name}
              active={category === name}
              onClick={() => setCategory(name)}
            >
              {name}
            </FilterChip>
          ))}
        </div>
      </div>

      {filtered.length === 0 && (
        <p className="py-20 text-center text-muted-foreground">
          Nothing matches “{query}”. Try a broader search.
        </p>
      )}

      <div className="space-y-14">
        {grouped.map(([categoryName, items]) => (
          <section key={categoryName}>
            <div className="mb-5 flex items-baseline gap-3">
              <h2 className="font-display text-xl font-semibold">{categoryName}</h2>
              <span className="h-px flex-1 bg-border" aria-hidden />
              <span className="text-xs text-muted-foreground tabular-nums">
                {items.length}
              </span>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {items.map((domain) => {
                const domainTracks = tracksByDomain.get(domain.slug) ?? [];
                const target = domainTracks[0];
                const totalConcepts = domainTracks.reduce(
                  (sum, t) => sum + t.concept_count,
                  0,
                );

                return (
                  <Link
                    key={domain.slug}
                    href={target ? `/onboarding?track=${target.slug}` : '/explore'}
                    className="group flex h-full flex-col rounded-lg border bg-card p-5 transition-colors hover:border-primary/60"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <DomainIcon
                        name={domain.icon}
                        className="h-5 w-5 shrink-0 text-primary"
                      />
                      {domainTracks.length > 1 && (
                        <span className="rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground">
                          {domainTracks.length} routes
                        </span>
                      )}
                    </div>

                    <h3 className="mt-4 font-display text-lg font-semibold group-hover:text-primary">
                      {domain.name}
                    </h3>
                    <p className="mt-1.5 line-clamp-2 flex-1 text-sm leading-relaxed text-muted-foreground">
                      {domain.description}
                    </p>

                    <div className="mt-4 flex items-center justify-between border-t pt-3">
                      <span className="text-xs text-muted-foreground tabular-nums">
                        {totalConcepts} concepts
                      </span>
                      <span className="flex items-center gap-1 text-xs font-medium text-primary">
                        Start
                        <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                      </span>
                    </div>
                  </Link>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
        active
          ? 'border-primary bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:border-primary/50 hover:text-foreground',
      )}
    >
      {children}
    </button>
  );
}
