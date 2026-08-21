'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Clock,
  Compass,
  Loader2,
  Route,
  Search,
  Target,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { ConceptSummary, Domain, TrackSummary } from '@/lib/types';

/**
 * Domain → route → pace → what you already know.
 *
 * The pace step names the commitment rather than asking for a number: people
 * know whether they can give this an evening or a workday, and they are far
 * more honest when the options say so out loud. The hours are still what the
 * scheduler packs weeks against — the label just maps to one.
 */
const PACES = [
  { value: 'casual', hours: 1, label: 'Casual', hint: 'An hour a day, around everything else' },
  { value: 'steady', hours: 2, label: 'Steady', hint: 'Two hours a day. Most people pick this' },
  { value: 'focused', hours: 4, label: 'Focused', hint: 'Half a working day, every day' },
  { value: 'intense', hours: 6, label: 'Intense', hint: 'This is the job until it is done' },
] as const;

type Pace = (typeof PACES)[number]['value'];

const STEPS = ['Domain', 'Route', 'Pace', 'Head start'] as const;

export function OnboardingWizard({
  domains,
  tracks,
  categories,
  preselectedSlug,
  initialPace,
}: {
  domains: Domain[];
  tracks: TrackSummary[];
  categories: string[];
  preselectedSlug?: string;
  initialPace: Pace;
}) {
  const router = useRouter();

  const preselectedDomain = preselectedSlug
    ? tracks.find((track) => track.slug === preselectedSlug)?.domain_slug
    : undefined;

  const [step, setStep] = useState(preselectedSlug ? 3 : 1);
  const [domainSlug, setDomainSlug] = useState(preselectedDomain ?? '');
  const [trackSlug, setTrackSlug] = useState(preselectedSlug ?? '');
  const [pace, setPace] = useState<Pace>(initialPace);
  const [known, setKnown] = useState<string[]>([]);
  const [concepts, setConcepts] = useState<ConceptSummary[]>([]);
  const [loadingConcepts, setLoadingConcepts] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<string | null>(null);

  const track = tracks.find((t) => t.slug === trackSlug);
  const hours = PACES.find((option) => option.value === pace)?.hours ?? 2;

  const tracksByDomain = useMemo(() => {
    const map = new Map<string, TrackSummary[]>();
    for (const t of tracks) {
      map.set(t.domain_slug, [...(map.get(t.domain_slug) ?? []), t]);
    }
    return map;
  }, [tracks]);

  const filteredDomains = useMemo(() => {
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
    const byCategory = new Map<string, Domain[]>();
    for (const domain of filteredDomains) {
      byCategory.set(domain.category, [...(byCategory.get(domain.category) ?? []), domain]);
    }
    return [...byCategory.entries()];
  }, [filteredDomains]);

  const domainTracks = tracks.filter((t) => t.domain_slug === domainSlug);

  const estimate = useMemo(() => {
    if (!track) return null;
    const weeks = Math.max(1, Math.ceil(track.total_hours / (hours * 7)));
    const finish = new Date();
    finish.setDate(finish.getDate() + weeks * 7);
    return { weeks, finish };
  }, [hours, track]);

  async function goToKnownStep() {
    setStep(4);
    if (concepts.length || !trackSlug) return;
    setLoadingConcepts(true);
    try {
      const response = await fetch(`/api/tracks/${trackSlug}`);
      if (response.ok) {
        const data = await response.json();
        setConcepts(data.concepts ?? []);
      }
    } finally {
      setLoadingConcepts(false);
    }
  }

  async function handleGenerate() {
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch('/api/roadmaps', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          track_slug: trackSlug,
          pace,
          known_concept_slugs: known,
        }),
      });
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

  function next() {
    if (step === 1) setStep(2);
    else if (step === 2) setStep(3);
    else if (step === 3) goToKnownStep();
  }

  const canAdvance =
    (step === 1 && Boolean(domainSlug)) ||
    (step === 2 && Boolean(trackSlug)) ||
    step === 3;

  return (
    <div className="w-full">
      <div className="flex justify-center w-full mb-12">
        <ol className="flex w-full max-w-xl items-center gap-2 px-2" aria-label="Progress">
        {STEPS.map((label, index) => {
          const n = index + 1;
          const isActive = n === step;
          const isCompleted = n < step;
          return (
            <li key={label} className="flex flex-1 items-center gap-3">
              <div className="relative flex flex-col items-center group">
                <span
                  className={cn(
                    'relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold transition-all duration-500',
                    isActive ? 'bg-primary text-primary-foreground shadow-[0_0_15px_rgba(255,255,255,0.3)] scale-110' 
                             : isCompleted ? 'bg-primary/20 text-primary border border-primary/30' 
                             : 'bg-muted/50 text-muted-foreground border border-border/50',
                  )}
                  aria-current={isActive ? 'step' : undefined}
                  title={label}
                >
                  {isCompleted ? <Check className="h-5 w-5" /> : n}
                </span>
                <span className={cn(
                  "absolute -bottom-6 text-xs font-medium whitespace-nowrap transition-colors duration-300",
                  isActive ? "text-primary" : "text-muted-foreground"
                )}>
                  {label}
                </span>
              </div>
              {n < STEPS.length && (
                <div className="h-[2px] flex-1 mx-2 overflow-hidden rounded-full bg-muted/30">
                  <div 
                    className="h-full bg-primary transition-all duration-700 ease-in-out" 
                    style={{ width: isCompleted ? '100%' : '0%' }} 
                  />
                </div>
              )}
            </li>
          );
        })}
      </ol>
      </div>

      <div className="relative rounded-3xl border border-white/5 bg-background/40 backdrop-blur-2xl p-8 md:p-12 shadow-2xl overflow-hidden">
        {/* Subtle background glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-32 bg-primary/5 blur-[100px] pointer-events-none -z-10" />
        {step === 1 && (
          <section>
            <h2 className="flex items-center gap-3 font-display text-3xl font-bold tracking-tight">
              <div className="p-2 rounded-xl bg-primary/10 border border-primary/20 text-primary">
                <Compass className="h-6 w-6" />
              </div>
              What do you want to learn?
            </h2>
            <p className="mt-3 mb-8 text-muted-foreground text-lg">
              Pick the field. We will narrow it down to a route on the next step.
            </p>

            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between mb-8">
              <div className="relative lg:w-96">
                <Search className="pointer-events-none absolute top-1/2 left-4 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search fields and routes…"
                  aria-label="Search fields"
                  className="w-full rounded-full border border-border/50 bg-card/40 py-2.5 pr-4 pl-11 text-sm outline-none focus-visible:ring-2 focus-visible:ring-primary backdrop-blur-sm transition-all"
                />
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setCategory(null)}
                  className={cn(
                    'rounded-full border px-4 py-1.5 text-xs font-semibold uppercase tracking-wider transition-all',
                    category === null
                      ? 'border-primary bg-primary text-primary-foreground shadow-[0_0_10px_rgba(255,255,255,0.2)]'
                      : 'border-border/50 bg-card/40 text-muted-foreground hover:border-primary/50 hover:text-foreground',
                  )}
                >
                  All
                </button>
                {categories.map((name) => (
                  <button
                    key={name}
                    type="button"
                    onClick={() => setCategory(name)}
                    className={cn(
                      'rounded-full border px-4 py-1.5 text-xs font-semibold uppercase tracking-wider transition-all',
                      category === name
                        ? 'border-primary bg-primary text-primary-foreground shadow-[0_0_10px_rgba(255,255,255,0.2)]'
                        : 'border-border/50 bg-card/40 text-muted-foreground hover:border-primary/50 hover:text-foreground',
                    )}
                  >
                    {name}
                  </button>
                ))}
              </div>
            </div>

            {grouped.length === 0 && (
              <div className="py-20 text-center">
                <p className="text-xl text-muted-foreground font-medium">
                  Nothing matches &ldquo;{query}&rdquo;.
                </p>
                <p className="text-sm text-muted-foreground/70 mt-2">Try a broader search or clear your filters.</p>
              </div>
            )}

            <div className="max-h-[32rem] space-y-8 overflow-y-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {grouped.map(([category, items]) => (
                <div key={category} className="animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-both">
                  <h3 className="text-sm font-semibold tracking-widest text-muted-foreground uppercase mb-4 pl-1">{category}</h3>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
                    {items.map((domain) => {
                      const isSelected = domainSlug === domain.slug;
                      return (
                        <button
                          key={domain.slug}
                          type="button"
                          disabled={!domain.has_content}
                          onClick={() => {
                            setDomainSlug(domain.slug);
                            setTrackSlug('');
                            setConcepts([]);
                          }}
                          aria-pressed={isSelected}
                          className={cn(
                            'group relative rounded-2xl border p-5 text-left transition-all duration-300 overflow-hidden',
                            isSelected
                              ? 'border-primary/50 bg-primary/10 shadow-[0_0_20px_rgba(255,255,255,0.05)] scale-[1.02]'
                              : 'border-border/40 bg-card/20 hover:bg-card/60 hover:border-border hover:scale-[1.01]',
                            !domain.has_content && 'cursor-not-allowed opacity-40 hover:scale-100 hover:bg-transparent grayscale',
                          )}
                        >
                          {isSelected && (
                            <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent opacity-50 pointer-events-none" />
                          )}
                          <span className={cn("block font-bold text-lg transition-colors", isSelected ? "text-primary" : "text-foreground group-hover:text-primary/80")}>
                            {domain.name}
                          </span>
                          <span className="mt-2 line-clamp-2 block text-sm text-muted-foreground/80 leading-relaxed">
                            {domain.has_content ? domain.description : 'Coming soon'}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {step === 2 && (
          <section>
            <h2 className="flex items-center gap-3 font-display text-3xl font-bold tracking-tight">
              <div className="p-2 rounded-xl bg-primary/10 border border-primary/20 text-primary">
                <Target className="h-6 w-6" />
              </div>
              Which route through it?
            </h2>
            <p className="mt-3 mb-8 text-muted-foreground text-lg">
              Each route is a prerequisite graph, ordered so nothing arrives before the thing
              it depends on.
            </p>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-both max-h-[32rem] overflow-y-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {domainTracks.map((option) => {
                const isSelected = trackSlug === option.slug;
                return (
                  <button
                    key={option.slug}
                    type="button"
                    onClick={() => {
                      setTrackSlug(option.slug);
                      setConcepts([]);
                      setKnown([]);
                    }}
                    aria-pressed={isSelected}
                    className={cn(
                      'group relative rounded-2xl border p-6 text-left transition-all duration-300 overflow-hidden flex flex-col sm:flex-row sm:items-center justify-between gap-4',
                      isSelected
                        ? 'border-primary/50 bg-primary/10 shadow-[0_0_20px_rgba(255,255,255,0.05)] scale-[1.02]'
                        : 'border-border/40 bg-card/20 hover:bg-card/60 hover:border-border hover:scale-[1.01]',
                    )}
                  >
                    {isSelected && (
                      <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-transparent opacity-50 pointer-events-none" />
                    )}
                    <div className="flex-1 relative z-10">
                      <h3 className={cn("font-bold text-xl transition-colors", isSelected ? "text-primary" : "text-foreground group-hover:text-primary/80")}>
                        {option.title}
                      </h3>
                      <p className="mt-2 line-clamp-2 text-sm text-muted-foreground/80 leading-relaxed">
                        {option.description}
                      </p>
                      <p className="mt-4 text-xs font-semibold tracking-wide text-muted-foreground uppercase flex gap-3">
                        <span>{option.concept_count} concepts</span>
                        <span>•</span>
                        <span>~{option.total_hours} hours</span>
                        <span>•</span>
                        <span className={cn(
                          option.difficulty === 'beginner' ? 'text-green-500/80' : 
                          option.difficulty === 'intermediate' ? 'text-amber-500/80' : 'text-red-500/80'
                        )}>{option.difficulty}</span>
                      </p>
                    </div>
                    <div className="shrink-0 flex items-center justify-center">
                      <div className={cn(
                        "h-8 w-8 rounded-full border-2 flex items-center justify-center transition-all duration-300",
                        isSelected ? "border-primary bg-primary text-primary-foreground scale-110" : "border-muted-foreground/30 text-transparent group-hover:border-primary/50"
                      )}>
                        <Check className="h-5 w-5" />
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {step === 3 && (
          <section>
            <h2 className="flex items-center gap-3 font-display text-3xl font-bold tracking-tight">
              <div className="p-2 rounded-xl bg-primary/10 border border-primary/20 text-primary">
                <Clock className="h-6 w-6" />
              </div>
              What pace can you keep?
            </h2>
            <p className="mt-3 mb-8 text-muted-foreground text-lg">
              Be honest rather than optimistic — the plan is only useful if you can hold it.
              You can change this later.
            </p>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-both">
              {PACES.map((option) => {
                const isSelected = pace === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setPace(option.value)}
                    aria-pressed={isSelected}
                    className={cn(
                      'group relative rounded-2xl border p-5 text-left transition-all duration-300 overflow-hidden',
                      isSelected
                        ? 'border-primary/50 bg-primary/10 shadow-[0_0_20px_rgba(255,255,255,0.05)] scale-[1.02]'
                        : 'border-border/40 bg-card/20 hover:bg-card/60 hover:border-border hover:scale-[1.01]',
                    )}
                  >
                    {isSelected && (
                      <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent opacity-50 pointer-events-none" />
                    )}
                    <div className="relative z-10">
                      <span className="flex items-baseline justify-between gap-2">
                        <span className={cn("text-xl font-bold transition-colors", isSelected ? "text-primary" : "text-foreground group-hover:text-primary/80")}>
                          {option.label}
                        </span>
                        <span className="text-sm font-semibold tracking-wider text-muted-foreground/70 uppercase">
                          {option.hours}h / day
                        </span>
                      </span>
                      <span className="mt-2 block text-sm text-muted-foreground/80 leading-relaxed">
                        {option.hint}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>

            {estimate && (
              <div className="mt-8 relative overflow-hidden rounded-2xl border border-primary/20 bg-primary/5 p-6 animate-in fade-in slide-in-from-bottom-4 duration-700 fill-mode-both delay-150">
                <div className="absolute top-0 left-0 w-1 h-full bg-primary" />
                <div className="flex items-start gap-4 relative z-10">
                  <div className="mt-1 p-2 bg-primary/20 rounded-full text-primary">
                    <Route className="h-5 w-5" />
                  </div>
                  <p className="text-muted-foreground leading-relaxed text-lg">
                    At this pace <strong className="text-foreground font-bold">{track?.title}</strong> takes
                    about <strong className="text-foreground font-bold">{estimate.weeks} weeks</strong> —
                    finishing around{' '}
                    <strong className="text-foreground font-bold" suppressHydrationWarning>
                      {estimate.finish.toLocaleDateString(undefined, {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric',
                      })}
                    </strong>
                    , before we subtract anything you already know.
                  </p>
                </div>
              </div>
            )}
          </section>
        )}

        {step === 4 && (
          <section>
            <h2 className="flex items-center gap-3 font-display text-3xl font-bold tracking-tight">
              <div className="p-2 rounded-xl bg-primary/10 border border-primary/20 text-primary">
                <Check className="h-6 w-6" />
              </div>
              Anything you already know?
            </h2>
            <p className="mt-3 mb-8 text-muted-foreground text-lg">
              Tick what you are already comfortable with and we will skip it — including
              anything that only existed as a prerequisite.
            </p>

            {loadingConcepts ? (
              <div className="flex flex-col items-center justify-center py-16 animate-in fade-in duration-500">
                <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
                <p className="text-muted-foreground font-medium">Scanning syllabus...</p>
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-both max-h-[32rem] overflow-y-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                {concepts.map((concept) => {
                  const checked = known.includes(concept.slug);
                  return (
                    <label
                      key={concept.slug}
                      className={cn(
                        'flex cursor-pointer items-center gap-4 rounded-2xl border p-4 transition-all duration-300',
                        checked 
                          ? 'border-primary/50 bg-primary/10 shadow-[0_0_15px_rgba(255,255,255,0.05)]' 
                          : 'border-border/40 bg-card/20 hover:bg-card/60 hover:border-border',
                      )}
                    >
                      <div className="relative flex items-center justify-center h-6 w-6 shrink-0">
                        <input
                          type="checkbox"
                          className="peer sr-only"
                          checked={checked}
                          onChange={(event) =>
                            setKnown((prev) =>
                              event.target.checked
                                ? [...prev, concept.slug]
                                : prev.filter((slug) => slug !== concept.slug),
                            )
                          }
                        />
                        <div className="h-6 w-6 rounded-md border-2 border-muted-foreground/30 peer-checked:border-primary peer-checked:bg-primary transition-all duration-200 flex items-center justify-center">
                          {checked && <Check className="h-4 w-4 text-primary-foreground scale-in-center" />}
                        </div>
                      </div>
                      <span className={cn("flex-1 font-semibold transition-colors", checked ? "text-primary" : "text-foreground")}>
                        {concept.name}
                      </span>
                      <span className="text-sm font-semibold text-muted-foreground/70 uppercase tracking-wide">
                        {concept.est_hours}h
                      </span>
                    </label>
                  );
                })}
              </div>
            )}

            <div className="mt-6 p-4 rounded-xl bg-card/40 border border-white/5 flex items-center justify-between">
              <p className="text-sm font-medium text-muted-foreground">
                {known.length === 0
                  ? 'Starting from scratch — nothing skipped.'
                  : `Skipping ${known.length} concept${known.length === 1 ? '' : 's'}.`}
              </p>
              {known.length > 0 && (
                <button 
                  onClick={() => setKnown([])}
                  className="text-xs font-bold uppercase tracking-wider text-muted-foreground hover:text-primary transition-colors"
                >
                  Clear all
                </button>
              )}
            </div>
          </section>
        )}

        {error && (
          <p
            role="alert"
            className="mt-6 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            {error}
          </p>
        )}

        <div className="mt-12 pt-6 border-t border-border/40 flex items-center justify-between gap-4">
          <Button
            variant="outline"
            size="lg"
            onClick={() => setStep((s) => Math.max(1, s - 1))}
            disabled={step === 1 || submitting}
            className="rounded-full px-6 font-semibold hover:bg-card/80 transition-all border-border/50"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>

          {step < 4 ? (
            <Button 
              size="lg" 
              onClick={next} 
              disabled={!canAdvance}
              className="rounded-full px-8 font-bold text-md shadow-[0_0_20px_rgba(255,255,255,0.15)] hover:shadow-[0_0_30px_rgba(255,255,255,0.25)] transition-all hover:scale-105"
            >
              Next Step
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
          ) : (
            <Button 
              size="lg" 
              onClick={handleGenerate} 
              disabled={submitting}
              className="rounded-full px-8 font-bold text-md bg-foreground text-background shadow-[0_0_25px_rgba(255,255,255,0.3)] hover:shadow-[0_0_40px_rgba(255,255,255,0.5)] hover:bg-foreground/90 transition-all hover:scale-105 relative overflow-hidden group"
            >
              <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700 ease-in-out" />
              {submitting ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Plotting your route…
                </>
              ) : (
                <>
                  Plot my route
                  <ArrowRight className="ml-2 h-5 w-5 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
