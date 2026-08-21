'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, Plus, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

import type { CompanyRoleRef, StageInfo } from './types';

type SeededCompany = { slug: string; name: string };

/**
 * Add an application by hand.
 *
 * There is deliberately no "paste a link and we will fill this in" button.
 * SkillAtlas does not fetch job listings — the learner pastes what they already
 * have, and `source_url` is a bookmark for them, not an input to a crawler.
 */
export function NewApplicationForm({
  companies,
  stages,
}: {
  companies: SeededCompany[];
  stages: StageInfo[];
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [companyName, setCompanyName] = useState('');
  const [roleTitle, setRoleTitle] = useState('');
  const [companySlug, setCompanySlug] = useState('');
  const [roleSlug, setRoleSlug] = useState('');
  const [roles, setRoles] = useState<CompanyRoleRef[]>([]);
  const [stage, setStage] = useState('saved');
  const [appliedOn, setAppliedOn] = useState('');
  const [location, setLocation] = useState('');
  const [salary, setSalary] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [notes, setNotes] = useState('');

  async function pickCompany(slug: string) {
    setCompanySlug(slug);
    setRoleSlug('');
    setRoles([]);
    if (!slug) return;

    const company = companies.find((c) => c.slug === slug);
    if (company) setCompanyName(company.name);

    // Only the seeded roles are fetched, and only from our own API.
    const response = await fetch(`/api/companies/${slug}`);
    if (!response.ok) return;
    const detail = (await response.json()) as { roles: CompanyRoleRef[] };
    setRoles(detail.roles ?? []);
  }

  function pickRole(slug: string) {
    setRoleSlug(slug);
    const role = roles.find((r) => r.slug === slug);
    if (role) setRoleTitle(role.title);
  }

  function reset() {
    setCompanyName('');
    setRoleTitle('');
    setCompanySlug('');
    setRoleSlug('');
    setRoles([]);
    setStage('saved');
    setAppliedOn('');
    setLocation('');
    setSalary('');
    setSourceUrl('');
    setJobDescription('');
    setNotes('');
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const response = await fetch('/api/applications', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: companyName.trim() || null,
          role_title: roleTitle.trim() || null,
          company_slug: companySlug || null,
          company_role_slug: roleSlug || null,
          stage,
          applied_on: appliedOn || null,
          location: location.trim() || null,
          salary_note: salary.trim() || null,
          source_url: sourceUrl.trim() || null,
          job_description: jobDescription.trim() || null,
          notes: notes.trim() || null,
        }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(
          typeof data.detail === 'string'
            ? data.detail
            : 'Could not save that application.',
        );
        return;
      }
      reset();
      setOpen(false);
      router.refresh();
    } catch {
      setError('Could not reach the server.');
    } finally {
      setPending(false);
    }
  }

  if (!open) {
    return (
      <Button onClick={() => setOpen(true)}>
        <Plus />
        Track an application
      </Button>
    );
  }

  return (
    <form onSubmit={submit} className="rounded-xl border bg-card p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-semibold">Track an application</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Anywhere you applied — the 30 companies we have researched are only a
            shortcut for the prep material.
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="Close"
          onClick={() => setOpen(false)}
        >
          <X />
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Company" htmlFor="company_name">
          <Input
            id="company_name"
            required
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            placeholder="Zoho, a 12-person startup, anyone"
          />
        </Field>

        <Field label="Role" htmlFor="role_title">
          <Input
            id="role_title"
            required
            value={roleTitle}
            onChange={(e) => setRoleTitle(e.target.value)}
            placeholder="Backend Engineer"
          />
        </Field>

        <Field
          label="Link a researched company"
          htmlFor="company_slug"
          hint="Optional. Unlocks their documented interview loop and your gaps for it."
        >
          <Select
            id="company_slug"
            value={companySlug}
            onChange={(e) => pickCompany(e.target.value)}
          >
            <option value="">Not one of them</option>
            {companies.map((company) => (
              <option key={company.slug} value={company.slug}>
                {company.name}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Their role" htmlFor="role_slug" hint="Optional.">
          <Select
            id="role_slug"
            value={roleSlug}
            disabled={roles.length === 0}
            onChange={(e) => pickRole(e.target.value)}
          >
            <option value="">
              {companySlug ? 'Not listed' : 'Pick a company first'}
            </option>
            {roles.map((role) => (
              <option key={role.slug} value={role.slug}>
                {role.title}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Stage" htmlFor="stage">
          <Select id="stage" value={stage} onChange={(e) => setStage(e.target.value)}>
            {stages.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Applied on" htmlFor="applied_on">
          <Input
            id="applied_on"
            type="date"
            value={appliedOn}
            onChange={(e) => setAppliedOn(e.target.value)}
          />
        </Field>

        <Field label="Location" htmlFor="location">
          <Input
            id="location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Remote, Bengaluru…"
          />
        </Field>

        <Field label="Salary" htmlFor="salary" hint="However it was quoted to you.">
          <Input
            id="salary"
            value={salary}
            onChange={(e) => setSalary(e.target.value)}
            placeholder="₹18 LPA, not disclosed…"
          />
        </Field>

        <Field
          label="Link to the posting"
          htmlFor="source_url"
          hint="Kept so you can click back to it. Never fetched."
          className="sm:col-span-2"
        >
          <Input
            id="source_url"
            type="url"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            placeholder="https://…"
          />
        </Field>

        <Field
          label="Job description"
          htmlFor="job_description"
          hint="Paste it — we do not read the listing for you."
          className="sm:col-span-2"
        >
          <Textarea
            id="job_description"
            rows={5}
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Paste the description you were sent or saw."
          />
        </Field>

        <Field label="Notes" htmlFor="notes" className="sm:col-span-2">
          <Textarea
            id="notes"
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Referred by…, recruiter's name, what to follow up on."
          />
        </Field>
      </div>

      {error && (
        <p role="alert" className="mt-4 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="mt-5 flex items-center gap-2">
        <Button type="submit" disabled={pending || !companyName.trim() || !roleTitle.trim()}>
          {pending ? <Loader2 className="animate-spin" /> : <Plus />}
          Add to the board
        </Button>
        <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function Field({
  label,
  htmlFor,
  hint,
  className,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <label htmlFor={htmlFor} className="text-sm font-medium">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function Select({ className, ...props }: React.ComponentProps<'select'>) {
  return (
    <select
      {...props}
      className={cn(
        'h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30',
        className,
      )}
    />
  );
}
