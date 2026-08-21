'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, Pencil, Trash2, Unlink } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

import type { ApplicationDetail } from '../types';

/**
 * Edit one application's details, unlink its company, or drop it.
 *
 * Stage moves are not here — they go through `StageControl`, so that every move
 * lands in the timeline instead of being quietly overwritten by a form save.
 */
export function ApplicationEditor({ application }: { application: ApplicationDetail }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [companyName, setCompanyName] = useState(application.company_name);
  const [roleTitle, setRoleTitle] = useState(application.role_title);
  const [location, setLocation] = useState(application.location ?? '');
  const [salary, setSalary] = useState(application.salary_note ?? '');
  const [sourceUrl, setSourceUrl] = useState(application.source_url ?? '');
  const [appliedOn, setAppliedOn] = useState(application.applied_on ?? '');
  const [jobDescription, setJobDescription] = useState(application.job_description ?? '');
  const [notes, setNotes] = useState(application.notes ?? '');

  async function send(body: Record<string, unknown>, method: 'PATCH' | 'DELETE') {
    setPending(true);
    setError(null);
    try {
      const response = await fetch(`/api/applications/${application.id}`, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: method === 'DELETE' ? undefined : JSON.stringify(body),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(
          typeof data.detail === 'string' ? data.detail : 'Could not save that.',
        );
        return false;
      }
      return true;
    } catch {
      setError('Could not reach the server.');
      return false;
    } finally {
      setPending(false);
    }
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    const ok = await send(
      {
        company_name: companyName.trim(),
        role_title: roleTitle.trim(),
        location: location.trim() || null,
        salary_note: salary.trim() || null,
        source_url: sourceUrl.trim() || null,
        applied_on: appliedOn || null,
        job_description: jobDescription.trim() || null,
        notes: notes.trim() || null,
      },
      'PATCH',
    );
    if (ok) {
      setOpen(false);
      router.refresh();
    }
  }

  async function unlink() {
    if (await send({ unlink_company: true }, 'PATCH')) router.refresh();
  }

  async function drop() {
    if (await send({}, 'DELETE')) router.push('/applications');
  }

  if (!open) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
          <Pencil />
          Edit details
        </Button>
        {application.company && (
          <Button variant="ghost" size="sm" disabled={pending} onClick={unlink}>
            <Unlink />
            Unlink {application.company.name}
          </Button>
        )}
        {confirming ? (
          <span className="inline-flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Delete this application?</span>
            <button
              type="button"
              disabled={pending}
              onClick={drop}
              className="font-medium text-destructive hover:underline disabled:opacity-50"
            >
              Delete
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              className="text-muted-foreground hover:underline"
            >
              Keep
            </button>
          </span>
        ) : (
          <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
            <Trash2 />
            Delete
          </Button>
        )}
        {error && (
          <span role="alert" className="text-sm text-destructive">
            {error}
          </span>
        )}
      </div>
    );
  }

  return (
    <form onSubmit={save} className="rounded-xl border bg-card p-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Company" htmlFor="edit_company">
          <Input
            id="edit_company"
            required
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
          />
        </Field>
        <Field label="Role" htmlFor="edit_role">
          <Input
            id="edit_role"
            required
            value={roleTitle}
            onChange={(e) => setRoleTitle(e.target.value)}
          />
        </Field>
        <Field label="Location" htmlFor="edit_location">
          <Input
            id="edit_location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
          />
        </Field>
        <Field label="Salary" htmlFor="edit_salary">
          <Input
            id="edit_salary"
            value={salary}
            onChange={(e) => setSalary(e.target.value)}
          />
        </Field>
        <Field label="Applied on" htmlFor="edit_applied_on">
          <Input
            id="edit_applied_on"
            type="date"
            value={appliedOn}
            onChange={(e) => setAppliedOn(e.target.value)}
          />
        </Field>
        <Field
          label="Link to the posting"
          htmlFor="edit_source"
          hint="Stored for you to click. Never fetched."
        >
          <Input
            id="edit_source"
            type="url"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
          />
        </Field>
        <Field
          label="Job description"
          htmlFor="edit_jd"
          hint="Paste it yourself — we do not read the listing."
          className="sm:col-span-2"
        >
          <Textarea
            id="edit_jd"
            rows={8}
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
          />
        </Field>
        <Field label="Notes" htmlFor="edit_notes" className="sm:col-span-2">
          <Textarea
            id="edit_notes"
            rows={4}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </Field>
      </div>

      {error && (
        <p role="alert" className="mt-4 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="mt-5 flex items-center gap-2">
        <Button type="submit" disabled={pending}>
          {pending && <Loader2 className="animate-spin" />}
          Save
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
