'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  ExternalLink,
  Flag,
  Loader2,
  Plus,
  ShieldAlert,
  SkipForward,
  WifiOff,
} from 'lucide-react';

import { Markdown } from '@/components/markdown';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

import {
  VERDICT_STYLE,
  type InterviewSession,
  type InterviewTurn,
  type SessionSummary,
} from '../types';

/**
 * Runs one mock interview: one question at a time, a verdict with reasons on
 * each answer, then a summary that hands back a list of concepts to study.
 *
 * The reference answer is not in the page until the answer is submitted — the
 * API withholds it, so it cannot be read out of the source either.
 */
export function InterviewRunner({ initial }: { initial: InterviewSession }) {
  const router = useRouter();
  const [turns, setTurns] = useState<InterviewTurn[]>(initial.turns);
  const [summary, setSummary] = useState<SessionSummary | null>(initial.summary);
  const [finished, setFinished] = useState(initial.status === 'completed');
  const [index, setIndex] = useState(() => {
    const next = initial.turns.findIndex((turn) => turn.verdict === null);
    return next === -1 ? Math.max(0, initial.turns.length - 1) : next;
  });
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const turn = turns[index];
  const answered = turns.filter((t) => t.verdict !== null).length;
  const allAnswered = answered === turns.length;

  async function submit(text: string) {
    if (pending || !turn) return;
    setPending(true);
    setError(null);
    try {
      const response = await fetch(
        `/api/interviews/sessions/${initial.id}/turns/${turn.id}/answer`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ answer: text }),
        },
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(data.detail ?? 'Could not submit that answer.');
        return;
      }
      setTurns((prev) => prev.map((t) => (t.id === data.id ? data : t)));
      setDraft('');
    } catch {
      setError('Could not reach the server.');
    } finally {
      setPending(false);
    }
  }

  async function finish() {
    setPending(true);
    setError(null);
    try {
      const response = await fetch(`/api/interviews/sessions/${initial.id}/complete`, {
        method: 'POST',
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(data.detail ?? 'Could not close the session.');
        return;
      }
      setTurns(data.turns);
      setSummary(data.summary);
      setFinished(true);
      router.refresh();
    } catch {
      setError('Could not reach the server.');
    } finally {
      setPending(false);
    }
  }

  if (finished && summary) {
    return <SessionReport session={initial} turns={turns} summary={summary} />;
  }

  return (
    <div>
      <header className="mb-6">
        <p className="eyebrow">{initial.company_name}</p>
        <h1 className="mt-2 font-display text-3xl font-semibold">{initial.role_title}</h1>
        {!initial.grading_available && (
          <p className="mt-4 flex items-start gap-2 rounded-lg border bg-muted/50 px-3 py-2 text-sm text-muted-foreground">
            <WifiOff className="mt-0.5 h-4 w-4 shrink-0" />
            Grading is unavailable — the local model is not reachable. Your answers are
            recorded and each question reveals its reference answer, but no score is being
            invented for them.
          </p>
        )}
      </header>

      <div className="mb-6 flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${(answered / turns.length) * 100}%` }}
          />
        </div>
        <span className="shrink-0 text-sm text-muted-foreground">
          {answered} / {turns.length}
        </span>
      </div>

      <nav className="mb-6 flex flex-wrap gap-1.5" aria-label="Questions">
        {turns.map((t, i) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setIndex(i)}
            aria-current={i === index}
            className={cn(
              'h-8 w-8 rounded-lg border text-sm transition-colors',
              i === index && 'border-primary text-primary',
              t.verdict && 'bg-muted/60',
              t.verdict === 'strong' && 'border-success/50 text-success',
              t.verdict === 'weak' && 'border-destructive/50 text-destructive',
            )}
          >
            {t.position}
          </button>
        ))}
      </nav>

      {turn && (
        <article className="rounded-xl border bg-card p-6">
          <div className="mb-4 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full border border-primary/40 bg-primary/10 px-2.5 py-1 font-medium text-primary">
              {turn.round_label}
            </span>
            <span className="rounded-full border px-2.5 py-1 text-muted-foreground">
              {turn.difficulty}
            </span>
            {turn.topic && (
              <span className="rounded-full border px-2.5 py-1 text-muted-foreground">
                {turn.topic}
              </span>
            )}
          </div>

          <p className="font-display text-xl leading-snug font-medium">{turn.question}</p>

          {turn.verdict === null ? (
            <div className="mt-6">
              <label htmlFor="answer" className="eyebrow mb-2 block">
                Your answer
              </label>
              <textarea
                id="answer"
                rows={9}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Answer as you would out loud — state your assumptions, then reason through it."
                className="w-full resize-y rounded-lg border bg-background p-3 text-sm leading-relaxed outline-none focus-visible:border-primary"
              />
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button size="lg" onClick={() => submit(draft)} disabled={pending || !draft.trim()}>
                  {pending ? <Loader2 className="animate-spin" /> : <Check />}
                  Submit answer
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => submit('')}
                  disabled={pending}
                  title="Record that you passed and reveal the reference answer"
                >
                  <SkipForward />
                  Pass on this one
                </Button>
              </div>
            </div>
          ) : (
            <TurnVerdict turn={turn} />
          )}

          {error && (
            <p
              role="alert"
              className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {error}
            </p>
          )}
        </article>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-3">
        {turn?.verdict !== null && index < turns.length - 1 && (
          <Button size="lg" onClick={() => setIndex(index + 1)}>
            Next question
            <ArrowRight />
          </Button>
        )}
        {answered > 0 && (
          <Button
            size="lg"
            variant={allAnswered ? 'default' : 'outline'}
            onClick={finish}
            disabled={pending}
          >
            {pending ? <Loader2 className="animate-spin" /> : <Flag />}
            {allAnswered ? 'Finish and see the feedback' : 'End early and see the feedback'}
          </Button>
        )}
      </div>
    </div>
  );
}

function TurnVerdict({ turn }: { turn: InterviewTurn }) {
  const style = VERDICT_STYLE[turn.verdict ?? 'ungraded'];
  return (
    <div className="mt-6 border-t pt-6">
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={cn(
            'rounded-full border px-3 py-1 text-sm font-medium',
            style.className,
          )}
        >
          {style.label}
        </span>
        {turn.score !== null && (
          <span className="font-display text-lg font-semibold">
            {turn.score}
            <span className="text-sm text-muted-foreground">/100</span>
          </span>
        )}
      </div>

      {turn.injection_flagged && (
        <p className="mt-4 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
          Your answer contained text addressed to the grader. It was graded as part of the
          answer, not acted on.
        </p>
      )}

      {turn.feedback_md && (
        <div className="mt-4 rounded-lg bg-muted/50 p-4 text-sm">
          <Markdown>{turn.feedback_md}</Markdown>
        </div>
      )}

      {turn.missed_points.length > 0 && (
        <div className="mt-4">
          <p className="eyebrow mb-2">What was missing</p>
          <ul className="ml-5 list-disc space-y-1 text-sm text-muted-foreground">
            {turn.missed_points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </div>
      )}

      {turn.reference_answer_md && (
        <details className="mt-5 rounded-lg border bg-background p-4" open={turn.score === null}>
          <summary className="cursor-pointer text-sm font-medium">
            <BookOpen className="mr-1.5 -mt-0.5 inline h-4 w-4" />
            Reference answer
          </summary>
          <div className="mt-3 text-sm">
            <Markdown>{turn.reference_answer_md}</Markdown>
          </div>
        </details>
      )}

      {turn.source_url && (
        <p className="mt-4 text-xs text-muted-foreground">
          Question sourced from{' '}
          <a
            href={turn.source_url}
            target="_blank"
            rel="noreferrer noopener"
            className="underline hover:text-foreground"
          >
            {turn.source_name}
            <ExternalLink className="ml-0.5 -mt-0.5 inline h-3 w-3" />
          </a>
        </p>
      )}
    </div>
  );
}

/** The end of the session: what went well, what did not, and what to go read. */
function SessionReport({
  session,
  turns,
  summary,
}: {
  session: InterviewSession;
  turns: InterviewTurn[];
  summary: SessionSummary;
}) {
  return (
    <div>
      <header className="mb-8 border-b pb-8">
        <p className="eyebrow">{session.company_name}</p>
        <h1 className="mt-2 font-display text-3xl font-semibold">
          {session.role_title} — debrief
        </h1>
        <div className="mt-5 flex flex-wrap items-end gap-8">
          <div>
            <p className="eyebrow">Score</p>
            {summary.score === null ? (
              <p className="mt-1 text-lg text-muted-foreground">Not graded</p>
            ) : (
              <p className="mt-1 font-display text-4xl font-semibold">
                {summary.score}
                <span className="text-lg text-muted-foreground">/100</span>
              </p>
            )}
          </div>
          <div>
            <p className="eyebrow">Answered</p>
            <p className="mt-1 font-display text-4xl font-semibold">
              {summary.answered_count}
              <span className="text-lg text-muted-foreground">
                /{summary.question_count}
              </span>
            </p>
          </div>
        </div>
        {summary.degraded && (
          <p className="mt-5 flex items-start gap-2 rounded-lg border bg-muted/50 px-3 py-2 text-sm text-muted-foreground">
            <WifiOff className="mt-0.5 h-4 w-4 shrink-0" />
            Part or all of this session ran without a model, so those answers have no
            verdict. The reference answers are on each question below.
          </p>
        )}
      </header>

      <div className="grid gap-6 sm:grid-cols-2">
        <section className="rounded-xl border bg-card p-5">
          <h2 className="eyebrow mb-3">What went well</h2>
          {summary.strengths.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nothing came out as a clear strength this time.
            </p>
          ) : (
            <ul className="space-y-2 text-sm">
              {summary.strengths.map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                  {item}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-xl border bg-card p-5">
          <h2 className="eyebrow mb-3">Where you lost ground</h2>
          {summary.weak_areas.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing flagged. Good loop.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {summary.weak_areas.map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-destructive" />
                  {item}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <StudyList concepts={summary.recommended_concepts} />

      <section className="mt-10">
        <h2 className="font-display text-xl font-semibold">Every question</h2>
        <div className="mt-4 space-y-4">
          {turns.map((turn) => (
            <article key={turn.id} className="rounded-xl border bg-card p-5">
              <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-full border px-2.5 py-1 text-muted-foreground">
                  {turn.round_label}
                </span>
                {turn.verdict && (
                  <span
                    className={cn(
                      'rounded-full border px-2.5 py-1 font-medium',
                      VERDICT_STYLE[turn.verdict].className,
                    )}
                  >
                    {VERDICT_STYLE[turn.verdict].label}
                  </span>
                )}
              </div>
              <p className="font-medium">{turn.question}</p>
              {turn.answer_text && (
                <p className="mt-3 rounded-lg bg-muted/50 p-3 text-sm whitespace-pre-wrap">
                  {turn.answer_text}
                </p>
              )}
              {turn.verdict && <TurnVerdict turn={turn} />}
            </article>
          ))}
        </div>
      </section>

      <div className="mt-10 flex flex-wrap gap-3 border-t pt-8">
        <Link
          href="/interviews"
          className="text-sm font-medium text-primary hover:underline"
        >
          Sit another loop
        </Link>
        <span className="text-muted-foreground">·</span>
        <Link href="/roadmap" className="text-sm font-medium text-primary hover:underline">
          Back to your route
        </Link>
      </div>
    </div>
  );
}

/**
 * The point of the whole feature: turn the debrief into study.
 *
 * Adds through the same endpoint the dashboard's "add a missing skill" uses, so
 * prerequisites are pulled in and the weeks are re-chunked properly.
 */
function StudyList({ concepts }: { concepts: SessionSummary['recommended_concepts'] }) {
  const router = useRouter();
  const addable = concepts.filter((c) => !c.in_roadmap);
  const [chosen, setChosen] = useState<string[]>(addable.map((c) => c.slug));
  const [state, setState] = useState<'idle' | 'saving' | 'done'>('idle');
  const [error, setError] = useState<string | null>(null);

  if (concepts.length === 0) return null;

  async function add() {
    setState('saving');
    setError(null);
    try {
      const response = await fetch('/api/roadmaps/current/items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ concept_slugs: chosen }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(
          data.detail ??
            'Could not add these to your route. Do you have a route built yet?',
        );
        setState('idle');
        return;
      }
      setState('done');
      router.refresh();
    } catch {
      setError('Could not reach the server.');
      setState('idle');
    }
  }

  return (
    <section className="mt-10 rounded-xl border bg-card p-6">
      <h2 className="font-display text-xl font-semibold">Go study this</h2>
      <p className="mt-1 mb-5 text-sm text-muted-foreground">
        Drawn from the concepts closest to what you were asked. A mock interview that does
        not send you back to the material is just a quiz.
      </p>

      <ul className="space-y-2">
        {concepts.map((concept) => {
          const picked = chosen.includes(concept.slug);
          return (
            <li
              key={concept.slug}
              className="flex items-start gap-3 rounded-lg border p-3 text-sm"
            >
              {!concept.in_roadmap && (
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 accent-[var(--primary)]"
                  checked={picked}
                  disabled={state !== 'idle'}
                  onChange={() =>
                    setChosen((prev) =>
                      picked
                        ? prev.filter((slug) => slug !== concept.slug)
                        : [...prev, concept.slug],
                    )
                  }
                />
              )}
              <div className="min-w-0 flex-1">
                <Link
                  href={`/concepts/${concept.slug}`}
                  className="font-medium hover:text-primary hover:underline"
                >
                  {concept.name}
                </Link>
                <p className="mt-0.5 text-muted-foreground">{concept.reason}</p>
              </div>
              {concept.in_roadmap && (
                <span className="shrink-0 text-xs text-muted-foreground">
                  already on your route
                </span>
              )}
              {concept.is_completed && !concept.in_roadmap && (
                <span className="shrink-0 text-xs text-muted-foreground">completed</span>
              )}
            </li>
          );
        })}
      </ul>

      {error && (
        <p
          role="alert"
          className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </p>
      )}

      {addable.length > 0 && (
        <div className="mt-5">
          {state === 'done' ? (
            <p className="flex items-center gap-2 text-sm font-medium text-success">
              <CheckCircle2 className="h-4 w-4" />
              Added to your route, with any prerequisites they need.{' '}
              <Link href="/roadmap" className="underline">
                See it
              </Link>
            </p>
          ) : (
            <Button onClick={add} disabled={state === 'saving' || chosen.length === 0}>
              {state === 'saving' ? <Loader2 className="animate-spin" /> : <Plus />}
              Add {chosen.length} to my route
            </Button>
          )}
        </div>
      )}
    </section>
  );
}
