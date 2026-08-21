import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';

import { AppShell } from '@/components/app-shell';
import { SiteHeader } from '@/components/site-header';
import { apiOrNull } from '@/lib/api';
import { requireUser } from '@/lib/dal';

import type { InterviewSession } from '../types';
import { InterviewRunner } from './interview-runner';

type Params = { params: Promise<{ sessionId: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { sessionId } = await params;
  const session = await apiOrNull<InterviewSession>(
    `/api/v1/interviews/sessions/${sessionId}`,
  );
  if (!session) return { title: 'Interview not found' };
  return { title: `${session.role_title} · ${session.company_name}` };
}

export default async function InterviewSessionPage({ params }: Params) {
  const { sessionId } = await params;
  await requireUser(`/interviews/${sessionId}`);

  const session = await apiOrNull<InterviewSession>(
    `/api/v1/interviews/sessions/${sessionId}`,
  );
  if (!session) notFound();

  return (
    <AppShell>
      <SiteHeader />

      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-10 sm:px-6">
        <nav className="mb-6 text-sm text-muted-foreground">
          <Link href="/interviews" className="hover:text-foreground">
            Mock interview
          </Link>
          <span className="mx-2">/</span>
          <Link
            href={`/companies/${session.company_slug}/${session.role_slug}`}
            className="hover:text-foreground"
          >
            {session.company_name}
          </Link>
          <span className="mx-2">/</span>
          <span className="text-foreground">{session.role_title}</span>
        </nav>

        <InterviewRunner initial={session} />
      </main>
    </AppShell>
  );
}
