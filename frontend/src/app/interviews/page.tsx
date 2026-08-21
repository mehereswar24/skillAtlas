import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowRight, Mic, WifiOff } from 'lucide-react';

import { AppShell } from '@/components/app-shell';
import { ButtonLink } from '@/components/button-link';
import { SiteHeader } from '@/components/site-header';
import { api, apiOrNull } from '@/lib/api';
import { requireUser } from '@/lib/dal';

import { InterviewSetup } from './interview-setup';
import type { InterviewRoleOption, InterviewStatus, SessionRow } from './types';

export const metadata: Metadata = {
  title: 'Mock interview',
  description:
    'Sit a real company loop from the question bank, get graded against that company’s rubric, and take the gaps back to your route.',
};

export default async function InterviewsPage() {
  await requireUser('/interviews');

  const [roles, sessions, status] = await Promise.all([
    api<InterviewRoleOption[]>('/api/v1/interviews/roles'),
    api<SessionRow[]>('/api/v1/interviews/sessions?limit=20'),
    apiOrNull<InterviewStatus>('/api/v1/interviews/status'),
  ]);

  const unfinished = sessions.filter((s) => s.status === 'in-progress');
  const finished = sessions.filter((s) => s.status === 'completed');

  return (
    <AppShell>
      <SiteHeader />

      <main className="flex-1 px-4 py-10 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <header className="mb-10 border-b pb-8">
            <p className="eyebrow">Before the real one</p>
            <h1 className="mt-3 font-display text-4xl font-semibold">Mock interview</h1>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              Sit a loop for a real role, drawn from the same source-cited question bank
              the company profiles show. Every answer is graded against what that company
              says it hires on — and the gaps come back as concepts you can add to your
              route.
            </p>
          </header>

          {status && !status.available && (
            <div
              role="status"
              className="mb-8 flex items-start gap-3 rounded-xl border border-border bg-muted/50 p-4 text-sm"
            >
              <WifiOff className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <div>
                <p className="font-medium">Grading is unavailable right now.</p>
                <p className="mt-1 text-muted-foreground">
                  The local model (Ollama) is not reachable, so nothing can judge your
                  answers. You can still sit the session — the questions are real and each
                  one reveals its reference answer — but no verdict or score will be
                  invented for you. Start Ollama with{' '}
                  <code className="rounded bg-muted px-1 py-0.5">ollama serve</code> for a
                  graded run.
                </p>
              </div>
            </div>
          )}

          {unfinished.length > 0 && (
            <section className="mb-10">
              <h2 className="eyebrow mb-3">Pick up where you left off</h2>
              <ul className="space-y-2">
                {unfinished.map((session) => (
                  <li key={session.id}>
                    <Link
                      href={`/interviews/${session.id}`}
                      className="group flex items-center justify-between rounded-xl border bg-card p-4 transition-colors hover:border-primary/60"
                    >
                      <span>
                        <span className="font-medium">{session.role_title}</span>
                        <span className="text-muted-foreground"> · {session.company_name}</span>
                        <span className="mt-0.5 block text-sm text-muted-foreground">
                          {session.answered_count} of {session.question_count} answered
                        </span>
                      </span>
                      <ArrowRight className="h-4 w-4 text-muted-foreground transition-colors group-hover:text-primary" />
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {roles.length === 0 ? (
            <div className="mx-auto max-w-md py-16 text-center">
              <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-lg border bg-card">
                <Mic className="h-6 w-6 text-primary" />
              </div>
              <h2 className="font-display text-2xl font-semibold">No question bank yet</h2>
              <p className="mt-3 text-muted-foreground">
                Mock interviews are drawn from the company question bank. Seed it with{' '}
                <code className="rounded bg-muted px-1.5 py-0.5 text-sm">
                  python -m app.seed.loader
                </code>{' '}
                in the backend.
              </p>
              <ButtonLink className="mt-8" href="/companies">
                Browse companies
              </ButtonLink>
            </div>
          ) : (
            <InterviewSetup roles={roles} gradingAvailable={status?.available ?? true} />
          )}

          {finished.length > 0 && (
            <section className="mt-14 border-t pt-10">
              <h2 className="font-display text-2xl font-semibold">Past attempts</h2>
              <p className="mt-1 mb-5 text-sm text-muted-foreground">
                Sitting the same loop twice draws a different paper, so a second score
                means something.
              </p>
              <ul className="divide-y rounded-xl border bg-card">
                {finished.map((session) => (
                  <li key={session.id}>
                    <Link
                      href={`/interviews/${session.id}`}
                      className="flex items-center justify-between gap-4 p-4 transition-colors hover:bg-muted/40"
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-medium">
                          {session.role_title}{' '}
                          <span className="font-normal text-muted-foreground">
                            · {session.company_name}
                          </span>
                        </span>
                        <span className="mt-0.5 block text-sm text-muted-foreground">
                          {new Date(session.created_at).toLocaleDateString()} ·{' '}
                          {session.answered_count}/{session.question_count} answered
                        </span>
                      </span>
                      <span className="shrink-0 text-right">
                        {session.score === null ? (
                          <span className="text-sm text-muted-foreground">
                            {session.was_degraded ? 'Not graded' : '—'}
                          </span>
                        ) : (
                          <span className="font-display text-xl font-semibold">
                            {session.score}
                            <span className="text-sm text-muted-foreground">/100</span>
                          </span>
                        )}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </main>
    </AppShell>
  );
}
