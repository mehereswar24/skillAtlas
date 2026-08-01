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
  preselectedSlug,
  initialPace,
}: {
  domains: Domain[];
  tracks: TrackSummary[];
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

  const track = tracks.find((t) => t.slug === trackSlug);
  const hours = PACES.find((option) => option.value === pace)?.hours ?? 2;

  // Only domains with a route behind them can be chosen; the rest are shown
  // greyed out rather than hidden, so the atlas still looks like the atlas.
  const grouped = useMemo(() => {
    const byCategory = new Map<string, Domain[]>();
    for (const domain of domains) {
      byCategory.set(domain.category, [...(byCategory.get(domain.category) ?? []), domain]);
    }
    return [...byCategory.entries()];
  }, [domains]);

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
    <div className="w-full max-w-2xl">
      <ol className="mb-8 flex items-center gap-2" aria-label="Progress">
        {STEPS.map((label, index) => {
          const n = index + 1;
          return (
            <li key={label} className="flex flex-1 items-center gap-2">
              <span
                className={cn(
                  'flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold',
                  n <= step ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground',
                )}
                aria-current={n === step ? 'step' : undefined}
                title={label}
              >
                {n < step ? <Check className="h-4 w-4" /> : n}
              </span>
              {n < STEPS.length && (
                <span className={cn('h-0.5 flex-1 rounded', n < step ? 'bg-primary' : 'bg-muted')} />
              )}
            </li>
          );
        })}
      </ol>

      <div className="rounded-lg border bg-card p-8">
        {step === 1 && (
          <section>
            <h2 className="flex items-center gap-2 font-display text-2xl font-semibold">
              <Compass className="h-5 w-5 text-primary" />
              What do you want to learn?
            </h2>
            <p className="mt-2 mb-6 text-muted-foreground">
              Pick the field. We will narrow it down to a route on the next step.
            </p>

            <div className="max-h-[26rem] space-y-6 overflow-y-auto pr-1">
              {grouped.map(([category, items]) => (
                <div key={category}>
                  <h3 className="eyebrow mb-2">{category}</h3>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {items.map((domain) => (
                      <button
                        key={domain.slug}
                        type="button"
                        disabled={!domain.has_content}
                        onClick={() => {
                          setDomainSlug(domain.slug);
                          setTrackSlug('');
                          setConcepts([]);
                        }}
                        aria-pressed={domainSlug === domain.slug}
                        className={cn(
                          'rounded-xl border p-4 text-left transition-all',
                          domainSlug === domain.slug
                            ? 'border-primary bg-primary/5 ring-1 ring-primary'
                            : 'hover:border-primary/50 hover:bg-muted/50',
                          !domain.has_content && 'cursor-not-allowed opacity-50 hover:border-border hover:bg-transparent',
                        )}
                      >
                        <span className="block font-semibold">{domain.name}</span>
                        <span className="mt-1 line-clamp-2 block text-sm text-muted-foreground">
                          {domain.has_content ? domain.description : 'Coming soon'}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {step === 2 && (
          <section>
            <h2 className="flex items-center gap-2 font-display text-2xl font-semibold">
              <Target className="h-5 w-5 text-primary" />
              Which route through it?
            </h2>
            <p className="mt-2 mb-6 text-muted-foreground">
              Each route is a prerequisite graph, ordered so nothing arrives before the thing
              it depends on.
            </p>

            <div className="grid gap-3">
              {domainTracks.map((option) => (
                <button
                  key={option.slug}
                  type="button"
                  onClick={() => {
                    setTrackSlug(option.slug);
                    setConcepts([]);
                    setKnown([]);
                  }}
                  aria-pressed={trackSlug === option.slug}
                  className={cn(
                    'rounded-xl border p-5 text-left transition-all',
                    trackSlug === option.slug
                      ? 'border-primary bg-primary/5 ring-1 ring-primary'
                      : 'hover:border-primary/50 hover:bg-muted/50',
                  )}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="font-semibold">{option.title}</h3>
                      <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                        {option.description}
                      </p>
                    </div>
                    {trackSlug === option.slug && <Check className="h-5 w-5 shrink-0 text-primary" />}
                  </div>
                  <p className="mt-3 text-xs font-medium text-muted-foreground tabular-nums">
                    {option.concept_count} concepts · ~{option.total_hours} hours ·{' '}
                    {option.difficulty}
                  </p>
                </button>
              ))}
            </div>
          </section>
        )}

        {step === 3 && (
          <section>
            <h2 className="flex items-center gap-2 font-display text-2xl font-semibold">
              <Clock className="h-5 w-5 text-primary" />
              What pace can you keep?
            </h2>
            <p className="mt-2 mb-6 text-muted-foreground">
              Be honest rather than optimistic — the plan is only useful if you can hold it.
              You can change this later.
            </p>

            <div className="grid gap-3 sm:grid-cols-2">
              {PACES.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setPace(option.value)}
                  aria-pressed={pace === option.value}
                  className={cn(
                    'rounded-xl border p-4 text-left transition-all',
                    pace === option.value
                      ? 'border-primary bg-primary/5 ring-1 ring-primary'
                      : 'hover:border-primary/50 hover:bg-muted/50',
                  )}
                >
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="text-lg font-bold">{option.label}</span>
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {option.hours}h / day
                    </span>
                  </span>
                  <span className="mt-1 block text-xs text-muted-foreground">{option.hint}</span>
                </button>
              ))}
            </div>

            {estimate && (
              <p className="mt-6 flex items-start gap-2 rounded-lg bg-muted/60 px-4 py-3 text-sm text-muted-foreground">
                <Route className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  At this pace <strong className="text-foreground">{track?.title}</strong> takes
                  about <strong className="text-foreground">{estimate.weeks} weeks</strong> —
                  finishing around{' '}
                  <strong className="text-foreground">
                    {estimate.finish.toLocaleDateString(undefined, {
                      day: 'numeric',
                      month: 'short',
                      year: 'numeric',
                    })}
                  </strong>
                  , before we subtract anything you already know.
                </span>
              </p>
            )}
          </section>
        )}

        {step === 4 && (
          <section>
            <h2 className="flex items-center gap-2 font-display text-2xl font-semibold">
              <Check className="h-5 w-5 text-primary" />
              Anything you already know?
            </h2>
            <p className="mt-2 mb-6 text-muted-foreground">
              Tick what you are already comfortable with and we will skip it — including
              anything that only existed as a prerequisite.
            </p>

            {loadingConcepts ? (
              <div className="flex justify-center py-10">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="grid max-h-80 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
                {concepts.map((concept) => {
                  const checked = known.includes(concept.slug);
                  return (
                    <label
                      key={concept.slug}
                      className={cn(
                        'flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm transition-colors',
                        checked ? 'border-primary bg-primary/5' : 'hover:bg-muted/50',
                      )}
                    >
                      <input
                        type="checkbox"
                        className="h-4 w-4 accent-[var(--primary)]"
                        checked={checked}
                        onChange={(event) =>
                          setKnown((prev) =>
                            event.target.checked
                              ? [...prev, concept.slug]
                              : prev.filter((slug) => slug !== concept.slug),
                          )
                        }
                      />
                      <span className="flex-1">{concept.name}</span>
                      <span className="text-xs text-muted-foreground tabular-nums">
                        {concept.est_hours}h
                      </span>
                    </label>
                  );
                })}
              </div>
            )}

            <p className="mt-4 text-sm text-muted-foreground">
              {known.length === 0
                ? 'Starting from scratch — nothing skipped.'
                : `Skipping ${known.length} concept${known.length === 1 ? '' : 's'}.`}
            </p>
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

        <div className="mt-8 flex items-center justify-between gap-3">
          <Button
            variant="ghost"
            onClick={() => setStep((s) => Math.max(1, s - 1))}
            disabled={step === 1 || submitting}
          >
            <ArrowLeft />
            Back
          </Button>

          {step < 4 ? (
            <Button size="lg" onClick={next} disabled={!canAdvance}>
              Next
              <ArrowRight />
            </Button>
          ) : (
            <Button size="lg" onClick={handleGenerate} disabled={submitting}>
              {submitting && <Loader2 className="animate-spin" />}
              {submitting ? 'Plotting your route…' : 'Plot my route'}
              {!submitting && <ArrowRight />}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
