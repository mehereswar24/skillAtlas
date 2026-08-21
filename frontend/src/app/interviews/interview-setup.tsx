'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, Mic } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

import type { InterviewRoleOption } from './types';

/**
 * Choose a company, a role, which rounds to sit, and how long.
 *
 * The round list is built from what the role actually has questions for — an
 * option that would produce an empty paper is never offered.
 */
export function InterviewSetup({
  roles,
  gradingAvailable,
}: {
  roles: InterviewRoleOption[];
  gradingAvailable: boolean;
}) {
  const router = useRouter();

  const companies = useMemo(() => {
    const seen = new Map<string, string>();
    for (const role of roles) seen.set(role.company_slug, role.company_name);
    return [...seen.entries()].map(([slug, name]) => ({ slug, name }));
  }, [roles]);

  const [companySlug, setCompanySlug] = useState(companies[0]?.slug ?? '');
  const forCompany = roles.filter((r) => r.company_slug === companySlug);
  const [roleSlug, setRoleSlug] = useState(forCompany[0]?.role_slug ?? '');

  const role = forCompany.find((r) => r.role_slug === roleSlug) ?? forCompany[0];
  const [excluded, setExcluded] = useState<string[]>([]);
  const [count, setCount] = useState(5);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chosenRounds = (role?.rounds ?? []).filter((r) => !excluded.includes(r.name));
  const available = chosenRounds.reduce((sum, r) => sum + r.question_count, 0);
  const maxCount = Math.min(10, Math.max(1, available));

  function pickCompany(slug: string) {
    setCompanySlug(slug);
    const first = roles.find((r) => r.company_slug === slug);
    setRoleSlug(first?.role_slug ?? '');
    setExcluded([]);
  }

  function pickRole(slug: string) {
    setRoleSlug(slug);
    setExcluded([]);
  }

  async function begin() {
    if (!role) return;
    setPending(true);
    setError(null);
    try {
      const response = await fetch('/api/interviews/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_slug: role.company_slug,
          role_slug: role.role_slug,
          question_count: Math.min(count, maxCount),
          // An empty list means the whole loop; only send a filter when the
          // learner actually narrowed it.
          rounds: excluded.length ? chosenRounds.map((r) => r.name) : [],
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(data.detail ?? 'Could not start the interview.');
        return;
      }
      router.push(`/interviews/${data.id}`);
    } catch {
      setError('Could not reach the server.');
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="rounded-xl border bg-card p-6">
      <h2 className="font-display text-xl font-semibold">Set up a session</h2>

      <div className="mt-6 grid gap-6 sm:grid-cols-2">
        <label className="block">
          <span className="eyebrow mb-2 block">Company</span>
          <select
            value={companySlug}
            onChange={(event) => pickCompany(event.target.value)}
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
          >
            {companies.map((company) => (
              <option key={company.slug} value={company.slug}>
                {company.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="eyebrow mb-2 block">Role</span>
          <select
            value={role?.role_slug ?? ''}
            onChange={(event) => pickRole(event.target.value)}
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
          >
            {forCompany.map((option) => (
              <option key={option.role_slug} value={option.role_slug}>
                {option.role_title} · {option.question_count} questions
              </option>
            ))}
          </select>
        </label>
      </div>

      {role && (
        <>
          {role.attempts > 0 && (
            <p className="mt-4 text-sm text-muted-foreground">
              You have sat this loop {role.attempts}{' '}
              {role.attempts === 1 ? 'time' : 'times'}
              {role.best_score !== null && <> · best {role.best_score}/100</>}.
            </p>
          )}

          <div className="mt-6">
            <p className="eyebrow mb-2">Rounds</p>
            <div className="flex flex-wrap gap-2">
              {role.rounds.map((round) => {
                const on = !excluded.includes(round.name);
                return (
                  <button
                    key={round.name}
                    type="button"
                    aria-pressed={on}
                    onClick={() =>
                      setExcluded((prev) =>
                        on
                          ? // Never let the learner deselect everything.
                            prev.length === role.rounds.length - 1
                            ? prev
                            : [...prev, round.name]
                          : prev.filter((name) => name !== round.name),
                      )
                    }
                    className={cn(
                      'rounded-full border px-3 py-1.5 text-sm transition-colors',
                      on
                        ? 'border-primary/50 bg-primary/10 text-primary'
                        : 'text-muted-foreground hover:bg-muted/50',
                    )}
                  >
                    {round.label}
                    <span className="ml-1.5 opacity-60">{round.question_count}</span>
                  </button>
                );
              })}
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              The session runs in loop order — the earlier rounds first, exactly as the
              company runs them.
            </p>
          </div>

          <div className="mt-6">
            <label className="eyebrow mb-2 block" htmlFor="question-count">
              Questions: {Math.min(count, maxCount)}
            </label>
            <input
              id="question-count"
              type="range"
              min={1}
              max={maxCount}
              value={Math.min(count, maxCount)}
              onChange={(event) => setCount(Number(event.target.value))}
              className="w-full max-w-xs accent-[var(--primary)]"
            />
            <p className="mt-1 text-sm text-muted-foreground">
              {available} banked for the rounds you picked.
            </p>
          </div>
        </>
      )}

      {error && (
        <p
          role="alert"
          className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </p>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-3 border-t pt-6">
        <Button size="lg" onClick={begin} disabled={pending || !role}>
          {pending ? <Loader2 className="animate-spin" /> : <Mic />}
          Start the interview
        </Button>
        {!gradingAvailable && (
          <span className="text-sm text-muted-foreground">
            Answers will be recorded and the reference answers shown, but not graded.
          </span>
        )}
      </div>
    </div>
  );
}
