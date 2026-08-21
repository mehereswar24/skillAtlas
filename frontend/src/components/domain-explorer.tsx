'use client';

import { useMemo, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import * as Icons from 'lucide-react';
import { ArrowRight, Search, ChevronDown, X } from 'lucide-react';

import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/lightswind/dropdown-menu';

import { cn } from '@/lib/utils';
import type { Domain, TrackSummary } from '@/lib/types';

function DomainIcon({
  name,
  className,
}: {
  name: string;
  className?: string;
}) {
  const Icon = (Icons as any)[name] || Icons.HelpCircle;
  return <Icon className={className} />;
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
  // The domain whose routes are on screen. A domain can hold twenty of them
  // (Backend does), so the card opens a list rather than guessing one.
  const [openDomain, setOpenDomain] = useState<Domain | null>(null);

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
        <ExpandableSearch 
          value={query}
          onChange={setQuery}
          placeholder="Search domains and routes…"
        />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-2 rounded-full border border-white/20 bg-card/40 px-5 py-2.5 text-sm font-medium text-foreground backdrop-blur-md transition-all hover:bg-black/20 hover:border-white/30 shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/50">
              {category || "All Categories"}
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48 bg-background/95 backdrop-blur-xl border border-white/20 rounded-xl p-1 shadow-2xl">
            <DropdownMenuItem 
              onClick={() => setCategory(null)}
              className="cursor-pointer rounded-lg px-3 py-2 transition-colors hover:bg-black/20"
            >
              <span className={cn("flex-1", category === null ? "font-semibold text-primary" : "text-muted-foreground")}>All Categories</span>
            </DropdownMenuItem>
            {categories.map((name) => (
              <DropdownMenuItem 
                key={name} 
                onClick={() => setCategory(name)}
                className="cursor-pointer rounded-lg px-3 py-2 transition-colors hover:bg-black/20"
              >
                <span className={cn("flex-1", category === name ? "font-semibold text-primary" : "text-muted-foreground")}>{name}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
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
                const totalConcepts = domainTracks.reduce(
                  (sum, t) => sum + t.concept_count,
                  0,
                );

                return (
                  <button
                    key={domain.slug}
                    type="button"
                    onClick={() => setOpenDomain(domain)}
                    disabled={domainTracks.length === 0}
                    className="group flex h-full flex-col rounded-lg border bg-card p-5 text-left transition-colors hover:border-primary/60 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <DomainIcon
                        name={domain.icon}
                        className="h-5 w-5 shrink-0 text-primary"
                      />
                      {domainTracks.length > 0 && (
                        <span className="rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground">
                          {domainTracks.length}{' '}
                          {domainTracks.length === 1 ? 'route' : 'routes'}
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
                        {domainTracks.length ? 'Browse routes' : 'Coming soon'}
                        <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>
        ))}
      </div>

      {openDomain && (
        <RoutePicker
          domain={openDomain}
          tracks={tracksByDomain.get(openDomain.slug) ?? []}
          onClose={() => setOpenDomain(null)}
        />
      )}
    </>
  );
}

const PACES = [
  { value: 'casual', label: 'Casual', hours: 1 },
  { value: 'steady', label: 'Steady', hours: 2 },
  { value: 'focused', label: 'Focused', hours: 4 },
  { value: 'intense', label: 'Intense', hours: 6 },
] as const;

/**
 * The routes inside one domain, and the one action that matters: start one.
 *
 * Starting posts to the BFF, which replaces any existing roadmap — so the
 * confirmation step is not decoration.
 */
function RoutePicker({
  domain,
  tracks,
  onClose,
}: {
  domain: Domain;
  tracks: TrackSummary[];
  onClose: () => void;
}) {
  const router = useRouter();
  const [selected, setSelected] = useState<TrackSummary | null>(null);
  const [pace, setPace] = useState<string>('steady');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The domain's own route leads, then its beginner variant, then everything
  // else alphabetically. Sorting by size alone put "Kotlin" above "Backend"
  // in the Backend domain, which reads like an accident.
  const ordered = useMemo(() => {
    const rank = (track: TrackSummary) => {
      if (track.slug === domain.slug) return 0;
      if (track.slug.startsWith(`${domain.slug}-`)) return 1;
      return 2;
    };
    return [...tracks].sort(
      (a, b) => rank(a) - rank(b) || a.title.localeCompare(b.title),
    );
  }, [tracks, domain.slug]);

  async function start(track: TrackSummary) {
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch('/api/roadmaps', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ track_slug: track.slug, pace }),
      });
      if (response.status === 401) {
        router.push(`/login?next=${encodeURIComponent('/explore')}`);
        return;
      }
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(data.detail ?? 'Could not build your roadmap. Please try again.');
        return;
      }
      router.push('/roadmap');
      router.refresh();
    } catch {
      setError('Could not reach the server. Is the backend running?');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 backdrop-blur-sm sm:items-center sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-label={`Routes in ${domain.name}`}
      onClick={onClose}
    >
      <div
        className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-t-2xl border bg-background shadow-2xl sm:rounded-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-4 border-b p-5">
          <div>
            <p className="eyebrow">{domain.category}</p>
            <h2 className="mt-1 font-display text-2xl font-semibold">{domain.name}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {ordered.length} {ordered.length === 1 ? 'route' : 'routes'}. Pick one to
              build a weekly plan.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-full border p-2 text-muted-foreground transition-colors hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <ul className="space-y-2">
            {ordered.map((track) => {
              const isSelected = selected?.slug === track.slug;
              return (
                <li key={track.slug}>
                  <button
                    type="button"
                    onClick={() => setSelected(isSelected ? null : track)}
                    aria-expanded={isSelected}
                    className={cn(
                      'w-full rounded-lg border p-4 text-left transition-colors',
                      isSelected
                        ? 'border-primary/60 bg-muted/40'
                        : 'hover:border-primary/40',
                    )}
                  >
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="font-medium">{track.title}</span>
                      <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                        {track.concept_count} concepts · {track.total_hours}h
                      </span>
                    </div>
                    {track.description && (
                      <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                        {track.description}
                      </p>
                    )}
                  </button>

                  {isSelected && (
                    <div className="mt-2 rounded-lg border border-dashed p-4">
                      <p className="text-xs font-medium text-muted-foreground">
                        How much time per day?
                      </p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {PACES.map((option) => (
                          <button
                            key={option.value}
                            type="button"
                            onClick={() => setPace(option.value)}
                            className={cn(
                              'rounded-full border px-3 py-1.5 text-xs transition-colors',
                              pace === option.value
                                ? 'border-primary bg-primary/10 font-semibold text-primary'
                                : 'text-muted-foreground hover:border-primary/40',
                            )}
                          >
                            {option.label} · {option.hours}h
                          </button>
                        ))}
                      </div>

                      {error && (
                        <p className="mt-3 text-sm text-destructive">{error}</p>
                      )}

                      <button
                        type="button"
                        disabled={submitting}
                        onClick={() => start(track)}
                        className="mt-4 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
                      >
                        {submitting ? 'Building your plan…' : 'Start this route'}
                        <ArrowRight className="h-4 w-4" />
                      </button>
                      <p className="mt-2 text-xs text-muted-foreground">
                        You can run several routes at once — this one becomes your
                        focus. Starting a route you already run rebuilds it around
                        what you have finished since.
                      </p>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
}

function ExpandableSearch({ 
  value, 
  onChange, 
  placeholder 
}: { 
  value: string; 
  onChange: (val: string) => void; 
  placeholder: string; 
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const isActive = isExpanded || value.length > 0;

  return (
    <motion.div 
      className="relative flex items-center rounded-full border border-white/20 bg-card/40 backdrop-blur-md overflow-hidden shadow-sm hover:border-white/30 transition-colors focus-within:ring-2 focus-within:ring-primary/50 focus-within:border-primary/50"
      initial={{ width: 44 }}
      animate={{ width: isActive ? 320 : 44 }}
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
    >
      <button 
        className="absolute left-0 z-10 flex h-11 w-11 items-center justify-center rounded-full hover:bg-white/5 transition-colors focus:outline-none"
        onClick={() => {
          setIsExpanded(true);
          inputRef.current?.focus();
        }}
        aria-label="Expand search"
      >
        <Search className="h-5 w-5 text-muted-foreground" />
      </button>
      
      <input
        ref={inputRef}
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setIsExpanded(true)}
        onBlur={() => setIsExpanded(false)}
        placeholder={placeholder}
        className="h-11 w-full bg-transparent pl-11 pr-4 text-sm outline-none placeholder:text-muted-foreground/60 text-foreground"
      />
    </motion.div>
  );
}
