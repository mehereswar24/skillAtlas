import type { Metadata } from 'next';

import { AppShell } from '@/components/app-shell';
import { SiteHeader } from '@/components/site-header';
import { api, apiOrNull } from '@/lib/api';
import { requireUser } from '@/lib/dal';

import { ResumeWorkspace } from './resume-client';
import type {
  ResumeProfile,
  ResumeStatus,
  ResumeUpload,
  RoleOption,
} from './resume-client';

export const metadata: Metadata = {
  title: 'Résumé',
  description:
    'A résumé built from what you have actually completed — and a review of the one you already have.',
};

type DashboardRoles = {
  roles: { slug: string; title: string; percent: number }[];
};

export default async function ResumePage() {
  const user = await requireUser('/resume');

  // Four independent reads; none of them blocks the others. `apiOrNull` on the
  // optional ones so a single 404 does not take the whole page down.
  const [status, profile, uploads, dashboard] = await Promise.all([
    apiOrNull<ResumeStatus>('/api/v1/resume/status'),
    apiOrNull<ResumeProfile>('/api/v1/resume/profile'),
    apiOrNull<ResumeUpload[]>('/api/v1/resume/uploads'),
    apiOrNull<DashboardRoles>('/api/v1/dashboard'),
  ]);

  const roles: RoleOption[] = (dashboard?.roles ?? []).map((role) => ({
    slug: role.slug,
    title: role.title,
    percent: role.percent,
  }));

  return (
    <AppShell>
      <SiteHeader />

      <main className="flex-1 px-4 py-10 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl space-y-8">
          <header className="border-b pb-8">
            <p className="eyebrow">Evidence, not self-report</p>
            <h1 className="mt-3 font-display text-4xl font-semibold">Résumé</h1>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              Everything on the generated résumé is already recorded against a passed
              quiz or a passing test run. Nothing on it is a claim you have to stand
              behind twice. You can also upload the résumé you already have and see
              what a parser makes of it.
            </p>
          </header>

          <ResumeWorkspace
            email={user.email}
            status={status}
            initialProfile={profile}
            initialUploads={uploads ?? []}
            roles={roles}
          />
        </div>
      </main>
    </AppShell>
  );
}
