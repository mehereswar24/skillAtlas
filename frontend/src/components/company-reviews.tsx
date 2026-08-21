'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Loader2, PenLine, Star, ThumbsDown, ThumbsUp, Trash2, X } from 'lucide-react';

import { formatRelative } from '@/components/community-feed';
import { Markdown } from '@/components/markdown';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import type {
  CompanyReview,
  CompanyReviewList,
  CompanyRoleSummary,
  ReviewOutcome,
} from '@/lib/types';

/**
 * Member-submitted reviews for a company.
 *
 * Everything else on the company page is researched: a "Last verified" date in
 * the header, a source link under every question. This section is the opposite
 * kind of claim, so it is walled off visually — its own heading, its own
 * "Member-submitted" badge, a muted panel rather than the page background, and
 * a line of copy that says in words that we did not verify any of it. Nothing
 * here should be mistakable for the sourced part above it.
 */

const OUTCOMES: { value: ReviewOutcome; label: string }[] = [
  { value: 'offer', label: 'Got an offer' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'withdrew', label: 'Withdrew' },
  { value: 'pending', label: 'Still in process' },
  { value: 'not-interviewed', label: 'Did not interview' },
];

const OUTCOME_LABEL = Object.fromEntries(OUTCOMES.map((o) => [o.value, o.label]));

const CURRENT_YEAR = new Date().getFullYear();

export function CompanyReviews({
  companySlug,
  companyName,
  roles,
  initial,
  signedIn,
}: {
  companySlug: string;
  companyName: string;
  roles: CompanyRoleSummary[];
  initial: CompanyReviewList;
  signedIn: boolean;
}) {
  const router = useRouter();
  const [data, setData] = useState(initial);
  const [editing, setEditing] = useState<CompanyReview | null>(null);
  const [composing, setComposing] = useState(false);
  // Deleting and voting are one-click actions with no form to report back
  // through. Without this a failed request is indistinguishable from a click
  // that never registered: the review just sits there and nothing is said.
  const [actionError, setActionError] = useState<string | null>(null);

  async function failureDetail(response: Response, fallback: string): Promise<string> {
    const body = await response.json().catch(() => null);
    return typeof body?.detail === 'string' ? body.detail : fallback;
  }

  async function reload() {
    const response = await fetch(`/api/companies/${companySlug}/reviews`);
    if (response.ok) setData(await response.json());
    // The company header shows the same average, and it is rendered on the
    // server — refresh so the two cannot disagree.
    router.refresh();
  }

  async function vote(review: CompanyReview, helpful: boolean) {
    if (!signedIn) {
      router.push(`/login?next=${encodeURIComponent(`/companies/${companySlug}`)}`);
      return;
    }
    setActionError(null);
    let response: Response;
    try {
      response = await fetch(
        `/api/reviews/${review.id}/vote?helpful=${helpful ? 'true' : 'false'}`,
        { method: 'POST' },
      );
    } catch {
      setActionError('Could not reach the server — your vote was not recorded.');
      return;
    }
    if (!response.ok) {
      setActionError(await failureDetail(response, 'Your vote could not be recorded.'));
      return;
    }
    const result = await response.json();
    setData((prev) => ({
      ...prev,
      reviews: prev.reviews.map((r) =>
        r.id === review.id
          ? {
              ...r,
              helpful_count: result.helpful_count,
              not_helpful_count: result.not_helpful_count,
              viewer_vote: result.viewer_vote,
            }
          : r,
      ),
    }));
  }

  async function remove(review: CompanyReview) {
    setActionError(null);
    let response: Response;
    try {
      response = await fetch(`/api/reviews/${review.id}`, { method: 'DELETE' });
    } catch {
      setActionError('Could not reach the server — your review was not deleted.');
      return;
    }
    if (!response.ok) {
      setActionError(
        await failureDetail(response, 'Your review could not be deleted. Nothing was changed.'),
      );
      return;
    }
    await reload();
  }

  const { summary } = data;
  const formOpen = composing || editing !== null;

  return (
    <section aria-labelledby="reviews-heading">
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <h2 id="reviews-heading" className="font-display text-2xl font-semibold">
          What members said
        </h2>
        <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-400">
          Member-submitted
        </span>
      </div>

      {/* The one sentence that keeps this section honest. */}
      <p className="mb-6 max-w-2xl text-sm text-muted-foreground">
        First-hand accounts written by learners. Unlike the profile above, none of this
        is researched or verified by SkillAtlas — treat each one as a single person&rsquo;s
        experience, not as fact about {companyName}.
      </p>

      <div className="rounded-2xl border bg-muted/30 p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <RatingSummaryPanel summary={summary} />

          {signedIn ? (
            data.viewer_can_write || editing ? (
              <Button
                onClick={() => {
                  // Closing is unconditional: while editing, this button reads
                  // "Cancel", and cancelling must close the form — not swap it
                  // for a blank write form the author is not allowed to submit
                  // (they already have a review; the POST would 409).
                  setEditing(null);
                  setComposing(formOpen ? false : true);
                }}
              >
                {formOpen ? <X /> : <PenLine />}
                {formOpen ? 'Cancel' : 'Write a review'}
              </Button>
            ) : (
              <p className="text-sm text-muted-foreground">
                You have reviewed {companyName}. Edit your review below.
              </p>
            )
          ) : (
            <Link
              href={`/login?next=${encodeURIComponent(`/companies/${companySlug}`)}`}
              className="text-sm font-medium text-primary hover:underline"
            >
              Sign in to write a review
            </Link>
          )}
        </div>

        {formOpen && (
          <ReviewForm
            // Remount when switching between "write" and "edit" so the fields
            // are seeded from the right review rather than kept from the last.
            key={editing?.id ?? 'new'}
            companySlug={companySlug}
            roles={roles}
            existing={editing}
            onDone={async () => {
              setComposing(false);
              setEditing(null);
              await reload();
            }}
          />
        )}

        {actionError && (
          <p
            role="alert"
            className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            {actionError}
          </p>
        )}

        {data.reviews.length === 0 ? (
          <p className="py-12 text-center text-sm text-muted-foreground">
            No member reviews yet.{' '}
            {signedIn
              ? 'If you have interviewed here, you would be the first.'
              : 'Sign in to write the first one.'}
          </p>
        ) : (
          <ul className="mt-6 space-y-4">
            {data.reviews.map((review) => (
              <ReviewCard
                key={review.id}
                review={review}
                signedIn={signedIn}
                onEdit={() => {
                  setComposing(false);
                  setEditing(review);
                }}
                onDelete={() => remove(review)}
                onVote={(helpful) => vote(review, helpful)}
              />
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

/* --- summary ------------------------------------------------------------- */

function RatingSummaryPanel({ summary }: { summary: CompanyReviewList['summary'] }) {
  if (summary.review_count === 0 || summary.average_rating === null) {
    return (
      <div>
        <p className="text-sm text-muted-foreground">No ratings yet</p>
      </div>
    );
  }

  const total = summary.review_count;

  return (
    <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
      <div>
        <div className="flex items-baseline gap-2">
          <span className="font-display text-4xl font-semibold tabular-nums">
            {summary.average_rating.toFixed(1)}
          </span>
          <span className="text-sm text-muted-foreground">/ 5</span>
        </div>
        <Stars value={Math.round(summary.average_rating)} />
        <p className="mt-1 text-xs text-muted-foreground tabular-nums">
          {total} {total === 1 ? 'review' : 'reviews'}
        </p>
      </div>

      <div className="min-w-[13rem] flex-1 space-y-1">
        {[5, 4, 3, 2, 1].map((star) => {
          const count = summary.distribution[String(star)] ?? 0;
          const percent = total > 0 ? (count / total) * 100 : 0;
          return (
            <div key={star} className="flex items-center gap-2 text-xs">
              <span className="w-3 text-right text-muted-foreground tabular-nums">
                {star}
              </span>
              <Star className="h-3 w-3 shrink-0 text-muted-foreground" />
              <div
                className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"
                role="img"
                aria-label={`${count} of ${total} reviews rated ${star} out of 5`}
              >
                <div
                  className="h-full rounded-full bg-amber-500 transition-all"
                  style={{ width: `${percent}%` }}
                />
              </div>
              <span className="w-5 text-right text-muted-foreground tabular-nums">
                {count}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Stars({ value }: { value: number }) {
  return (
    <div className="mt-1 flex gap-0.5" aria-label={`${value} out of 5`}>
      {[1, 2, 3, 4, 5].map((star) => (
        <Star
          key={star}
          aria-hidden
          className={cn(
            'h-3.5 w-3.5',
            star <= value ? 'fill-amber-500 text-amber-500' : 'text-muted-foreground/40',
          )}
        />
      ))}
    </div>
  );
}

/* --- one review ---------------------------------------------------------- */

function ReviewCard({
  review,
  signedIn,
  onEdit,
  onDelete,
  onVote,
}: {
  review: CompanyReview;
  signedIn: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onVote: (helpful: boolean) => void;
}) {
  const author = review.is_anonymous
    ? 'Anonymous'
    : (review.author.display_name ?? 'A member');

  return (
    <li className="rounded-xl border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Stars value={review.rating} />
          <h3 className="mt-2 font-semibold">{review.title}</h3>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Seeded demo content says so on its face. */}
          {review.is_sample && (
            <span className="rounded-full border border-dashed px-2 py-0.5 text-xs font-medium text-muted-foreground">
              Sample review
            </span>
          )}
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
            {OUTCOME_LABEL[review.interview_outcome] ?? review.interview_outcome}
          </span>
        </div>
      </div>

      <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
        <span>{author}</span>
        {review.role && (
          <>
            <span aria-hidden>·</span>
            <span>{review.role.title}</span>
          </>
        )}
        {review.interview_year && (
          <>
            <span aria-hidden>·</span>
            <span className="tabular-nums">interviewed {review.interview_year}</span>
          </>
        )}
        <span aria-hidden>·</span>
        <span>{formatRelative(review.created_at)}</span>
      </p>

      <Markdown className="mt-3 text-sm">{review.body_md}</Markdown>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t pt-3">
        {review.viewer_is_author ? (
          <>
            <Button size="sm" variant="outline" onClick={onEdit}>
              <PenLine />
              Edit
            </Button>
            <Button size="sm" variant="destructive" onClick={onDelete}>
              <Trash2 />
              Delete
            </Button>
            <span className="text-xs text-muted-foreground">This is your review.</span>
          </>
        ) : (
          <>
            <VoteButton
              active={review.viewer_vote === 1}
              count={review.helpful_count}
              label="Helpful"
              onClick={() => onVote(true)}
              icon={<ThumbsUp className="h-3.5 w-3.5" />}
            />
            <VoteButton
              active={review.viewer_vote === -1}
              count={review.not_helpful_count}
              label="Not helpful"
              onClick={() => onVote(false)}
              icon={<ThumbsDown className="h-3.5 w-3.5" />}
            />
            {!signedIn && (
              <span className="text-xs text-muted-foreground">Sign in to vote</span>
            )}
          </>
        )}
      </div>
    </li>
  );
}

function VoteButton({
  active,
  count,
  label,
  icon,
  onClick,
}: {
  active: boolean;
  count: number;
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={`${label} (${count})`}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium transition-colors',
        active
          ? 'bg-primary/10 text-primary'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      {icon}
      {label}
      <span className="tabular-nums">{count}</span>
    </button>
  );
}

/* --- the write/edit form ------------------------------------------------- */

function ReviewForm({
  companySlug,
  roles,
  existing,
  onDone,
}: {
  companySlug: string;
  roles: CompanyRoleSummary[];
  existing: CompanyReview | null;
  onDone: () => void;
}) {
  const [rating, setRating] = useState(existing?.rating ?? 0);
  const [title, setTitle] = useState(existing?.title ?? '');
  const [body, setBody] = useState(existing?.body_md ?? '');
  const [outcome, setOutcome] = useState<ReviewOutcome>(
    existing?.interview_outcome ?? 'not-interviewed',
  );
  const [year, setYear] = useState(existing?.interview_year?.toString() ?? '');
  const [roleSlug, setRoleSlug] = useState(existing?.role?.slug ?? '');
  const [anonymous, setAnonymous] = useState(existing?.is_anonymous ?? false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const payload = {
        rating,
        title,
        body_md: body,
        interview_outcome: outcome,
        interview_year: year ? Number(year) : null,
        is_anonymous: anonymous,
        role_slug: roleSlug || null,
      };
      const response = await fetch(
        existing ? `/api/reviews/${existing.id}` : `/api/companies/${companySlug}/reviews`,
        {
          method: existing ? 'PATCH' : 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
      );
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(
          typeof data.detail === 'string' ? data.detail : 'Could not save your review.',
        );
        return;
      }
      onDone();
    } catch {
      setError('Could not reach the server.');
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-6 space-y-4 rounded-xl border bg-card p-5">
      <p className="text-sm text-muted-foreground">
        Write about your own experience — what the rounds were like and what you wish you
        had prepared. Please leave out anything that identifies an individual
        interviewer.
      </p>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Your rating</legend>
        <div className="flex gap-1">
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              type="button"
              onClick={() => setRating(star)}
              aria-label={`${star} out of 5`}
              aria-pressed={rating === star}
              className="rounded p-0.5 transition-transform hover:scale-110 focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Star
                className={cn(
                  'h-6 w-6',
                  star <= rating
                    ? 'fill-amber-500 text-amber-500'
                    : 'text-muted-foreground/40',
                )}
              />
            </button>
          ))}
        </div>
      </fieldset>

      <div className="space-y-2">
        <Label htmlFor="review-title">Headline</Label>
        <Input
          id="review-title"
          required
          minLength={4}
          maxLength={200}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Four rounds, mostly about how you think"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="review-body">Your experience</Label>
        <Textarea
          id="review-body"
          required
          rows={6}
          minLength={20}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="What the process looked like, what was asked, and what you would revise first."
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-2">
          <Label htmlFor="review-outcome">Outcome</Label>
          <select
            id="review-outcome"
            value={outcome}
            onChange={(e) => setOutcome(e.target.value as ReviewOutcome)}
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {OUTCOMES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="review-role">Role (optional)</Label>
          <select
            id="review-role"
            value={roleSlug}
            onChange={(e) => setRoleSlug(e.target.value)}
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="">Not role-specific</option>
            {roles.map((role) => (
              <option key={role.slug} value={role.slug}>
                {role.title}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="review-year">Year (optional)</Label>
          <Input
            id="review-year"
            type="number"
            min={1990}
            max={CURRENT_YEAR + 1}
            value={year}
            onChange={(e) => setYear(e.target.value)}
            placeholder={String(CURRENT_YEAR)}
          />
        </div>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={anonymous}
          onChange={(e) => setAnonymous(e.target.checked)}
          className="h-4 w-4 rounded border-input"
        />
        Post anonymously — your name is withheld from everyone but you.
      </label>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <Button type="submit" disabled={pending || rating === 0 || title.length < 4 || body.trim().length < 20}>
        {pending && <Loader2 className="animate-spin" />}
        {existing ? 'Save changes' : 'Publish review'}
      </Button>
    </form>
  );
}
