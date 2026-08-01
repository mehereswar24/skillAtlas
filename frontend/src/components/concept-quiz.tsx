'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowRight,
  Check,
  CheckCircle2,
  Loader2,
  RotateCcw,
  Trophy,
  X,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { CompletionResult, QuizQuestion } from '@/lib/types';

/**
 * Quiz + "mark complete". Answers are graded on the server — the API never
 * sends which option is correct until a submission comes back, so the answers
 * cannot be read out of the page source.
 */
export function ConceptQuiz({
  slug,
  questions,
  alreadyCompleted,
  minutesSuggestion,
}: {
  slug: string;
  questions: QuizQuestion[];
  alreadyCompleted: boolean;
  minutesSuggestion: number;
}) {
  const router = useRouter();
  const [selected, setSelected] = useState<Record<number, number>>({});
  const [result, setResult] = useState<CompletionResult | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const answeredAll = questions.every((q) => selected[q.id] !== undefined);
  const reviewByQuestion = new Map(result?.review.map((r) => [r.question_id, r]) ?? []);

  async function submit() {
    setPending(true);
    setError(null);
    try {
      const response = await fetch(`/api/progress/${slug}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          answers: Object.entries(selected).map(([question_id, option_id]) => ({
            question_id: Number(question_id),
            option_id,
          })),
          time_spent_minutes: minutesSuggestion,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(data.detail ?? 'Could not record your progress.');
        return;
      }
      setResult(data);
      if (data.passed) router.refresh();
    } catch {
      setError('Could not reach the server.');
    } finally {
      setPending(false);
    }
  }

  function retry() {
    setSelected({});
    setResult(null);
    setError(null);
  }

  // No quiz authored for this concept — completion is a single button.
  if (questions.length === 0) {
    return (
      <div className="rounded-xl border bg-card p-6">
        {result?.passed || alreadyCompleted ? (
          <CompletedNotice result={result} />
        ) : (
          <>
            <h2 className="font-display text-xl font-semibold">Finished this one?</h2>
            <p className="mt-1 mb-4 text-sm text-muted-foreground">
              Mark it complete to unlock what depends on it and record the XP.
            </p>
            <Button onClick={submit} disabled={pending}>
              {pending ? <Loader2 className="animate-spin" /> : <Check />}
              Mark complete
            </Button>
            {error && <ErrorNote message={error} />}
          </>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-card p-6">
      <div className="mb-6 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-display text-xl font-semibold">Check your understanding</h2>
        <p className="text-sm text-muted-foreground">
          {questions.length} questions · two thirds correct to pass
        </p>
      </div>

      <ol className="space-y-6">
        {questions.map((question, index) => {
          const review = reviewByQuestion.get(question.id);
          return (
            <li key={question.id}>
              <p className="mb-3 font-medium">
                <span className="mr-2 text-muted-foreground">{index + 1}.</span>
                {question.prompt}
              </p>

              <div className="space-y-2">
                {question.options.map((option) => {
                  const isSelected = selected[question.id] === option.id;
                  const isCorrect = review?.correct_option_id === option.id;
                  const isWrongPick = review && isSelected && !review.is_correct;

                  return (
                    <label
                      key={option.id}
                      className={cn(
                        'flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm transition-colors',
                        !review && isSelected && 'border-primary bg-primary/5',
                        !review && !isSelected && 'hover:bg-muted/50',
                        review && isCorrect && 'border-success/50 bg-success/10',
                        isWrongPick && 'border-destructive/50 bg-destructive/10',
                        review && 'cursor-default',
                      )}
                    >
                      <input
                        type="radio"
                        name={`q-${question.id}`}
                        className="mt-0.5 h-4 w-4 accent-[var(--primary)]"
                        checked={isSelected}
                        disabled={Boolean(review) || pending}
                        onChange={() =>
                          setSelected((prev) => ({ ...prev, [question.id]: option.id }))
                        }
                      />
                      <span className="flex-1">{option.text}</span>
                      {review && isCorrect && (
                        <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                      )}
                      {isWrongPick && <X className="h-4 w-4 shrink-0 text-destructive" />}
                    </label>
                  );
                })}
              </div>

              {review?.explanation && (
                <p className="mt-2 rounded-lg bg-muted/60 px-3 py-2 text-sm text-muted-foreground">
                  {review.explanation}
                </p>
              )}
            </li>
          );
        })}
      </ol>

      {error && <ErrorNote message={error} />}

      <div className="mt-6 border-t pt-6">
        {!result ? (
          <div className="flex flex-wrap items-center gap-3">
            <Button size="lg" onClick={submit} disabled={!answeredAll || pending}>
              {pending && <Loader2 className="animate-spin" />}
              {alreadyCompleted ? 'Submit again' : 'Submit and complete'}
            </Button>
            {!answeredAll && (
              <span className="text-sm text-muted-foreground">
                Answer every question to submit.
              </span>
            )}
          </div>
        ) : result.passed ? (
          <CompletedNotice result={result} />
        ) : (
          <div>
            <p className="font-semibold text-destructive">
              {result.correct_count} of {result.question_count} correct — not quite.
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              The correct answers are marked above with an explanation. Nothing was
              recorded, so read back through and try again.
            </p>
            <Button variant="outline" className="mt-4" onClick={retry}>
              <RotateCcw />
              Try again
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function CompletedNotice({ result }: { result: CompletionResult | null }) {
  return (
    <div>
      <p className="flex items-center gap-2 font-semibold text-success">
        <CheckCircle2 className="h-5 w-5" />
        {result
          ? `${result.correct_count} of ${result.question_count} correct — completed.`
          : 'You have already completed this concept.'}
      </p>

      {result && result.xp_earned > 0 && (
        <p className="mt-2 text-sm text-muted-foreground">
          <strong className="text-foreground">+{result.xp_earned} XP</strong> · level{' '}
          {result.level}
          {result.leveled_up && ' (levelled up!)'} · {result.streak_days} day streak
        </p>
      )}

      {result && result.new_badges.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {result.new_badges.map((badge) => (
            <span
              key={badge.slug}
              className="inline-flex items-center gap-1.5 rounded-full bg-primary/12 px-3 py-1 text-sm font-medium text-primary"
            >
              <Trophy className="h-3.5 w-3.5" />
              {badge.name}
            </span>
          ))}
        </div>
      )}

      {result && result.unlocked_concepts.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-sm font-medium">This just unlocked:</p>
          <div className="flex flex-wrap gap-2">
            {result.unlocked_concepts.map((concept) => (
              <Link
                key={concept.slug}
                href={`/concepts/${concept.slug}`}
                className="inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm transition-colors hover:border-primary hover:text-primary"
              >
                {concept.name}
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            ))}
          </div>
        </div>
      )}

      <Link
        href="/roadmap"
        className="mt-6 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
      >
        Back to your roadmap
        <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}

function ErrorNote({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
    >
      {message}
    </p>
  );
}
