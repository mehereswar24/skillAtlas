'use client';

import { useCallback, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  AlertTriangle,
  Building2,
  Check,
  CircleAlert,
  Eye,
  EyeOff,
  FileText,
  Loader2,
  Plus,
  Printer,
  Sparkles,
  Trash2,
  Upload,
  Wand2,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

// --------------------------------------------------------------------------
// shapes (mirrors backend/app/schemas/resume.py)
// --------------------------------------------------------------------------

export type ResumeStatus = {
  available: boolean;
  model: string | null;
  mode: string;
  max_upload_mb: number;
  accepted_kinds: string[];
};

export type ResumeProfile = {
  full_name: string | null;
  headline: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  links: string[];
  summary: string | null;
};

export type ResumeUpload = {
  id: number;
  filename: string;
  kind: string;
  size_bytes: number;
  extraction_ok: boolean;
  extraction_note: string | null;
  page_count: number | null;
  text_chars: number;
  created_at: string;
  has_analysis: boolean;
};

export type RoleOption = { slug: string; title: string; percent: number };

type ConceptRef = {
  slug: string;
  name: string;
  summary: string;
  est_hours: number;
  difficulty: string;
  domain_slug: string;
  domain_name: string;
};

type ResumeDocument = {
  summary: string;
  summary_is_generated: boolean;
  generated_by: string | null;
  degraded: boolean;
  header: { full_name: string; headline: string | null };
  target_role: { slug: string; title: string; percent: number } | null;
  stats: {
    concepts_completed: number;
    projects_shipped: number;
    hours_invested: number;
    xp: number;
    level: number;
    badges: number;
  };
  skills: { domain_slug: string; domain_name: string; concepts: ConceptRef[] }[];
  projects: {
    slug: string;
    title: string;
    tests_passed: number;
    tests_total: number;
    bullets: string[];
  }[];
  gaps: {
    concept: ConceptRef;
    percent_contribution: number;
    in_roadmap: boolean;
  }[];
  job_match: JobMatch | null;
};

type JobMatch = {
  coverage_percent: number;
  requirements_found: number;
  matched: { concept: ConceptRef; mentions: number }[];
  missing: { concept: ConceptRef; in_roadmap?: boolean }[];
  addable_slugs: string[];
  unmatched_terms: string[];
};

type Analysis = {
  degraded: boolean;
  generated_by: string | null;
  degraded_reason: string | null;
  extraction: { ok: boolean; note: string | null; kind: string; chars: number };
  ats: {
    file: { filename: string; kind: string; size_kb: number; pages: number | null };
    text_chars: number;
    word_count: number;
    can_extract: string[];
    cannot_extract: string[];
    warnings: string[];
    sections_detected: Record<string, boolean>;
  };
  suggestions: { kind: string; severity: string; message: string; evidence: string | null }[];
  rewrites: { original: string; rewrite: string; why: string }[];
  detected_skills: { concept: ConceptRef; mentions: number; source: string }[];
  career_options: {
    slug: string;
    title: string;
    description: string | null;
    percent: number;
    missing_count: number;
  }[];
  companies: {
    company_slug: string;
    company_name: string;
    role_title: string;
    level: string;
    hq: string | null;
    focus_areas: { label: string; concept_slug: string | null }[];
    sample_questions: {
      question: string;
      round: string;
      difficulty: string;
      source_name: string;
      source_url: string;
    }[];
  }[];
  learn_next: {
    concept: ConceptRef;
    role_title: string;
    percent_contribution: number;
    in_roadmap: boolean;
  }[];
  addable_slugs: string[];
  job_match: JobMatch | null;
  target_role: { slug: string; title: string; percent: number } | null;
};

// --------------------------------------------------------------------------
// small shared pieces
// --------------------------------------------------------------------------

function Section({
  title,
  description,
  children,
  className,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn('rounded-lg border bg-card p-6', className)}>
      <h2 className="font-display text-lg font-semibold">{title}</h2>
      {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Notice({
  tone,
  children,
}: {
  tone: 'warn' | 'info' | 'bad';
  children: React.ReactNode;
}) {
  const Icon = tone === 'bad' ? CircleAlert : tone === 'warn' ? AlertTriangle : Sparkles;
  return (
    <div
      role="status"
      className={cn(
        'flex items-start gap-3 rounded-lg border p-4 text-sm',
        tone === 'bad' && 'border-destructive/40 text-destructive',
        tone === 'warn' && 'border-amber-500/40',
        tone === 'info' && 'border-dashed',
      )}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

/** Appends concepts to the active route. Same endpoint the dashboard uses. */
function AddToRoute({ slugs, label = 'Add to my route' }: { slugs: string[]; label?: string }) {
  const router = useRouter();
  const [state, setState] = useState<'idle' | 'pending' | 'done' | 'error'>('idle');

  if (slugs.length === 0) return null;

  if (state === 'done') {
    return (
      <p className="flex items-center gap-2 text-sm text-success">
        <Check className="h-4 w-4" /> Added to your route
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <Button
        variant="secondary"
        size="sm"
        disabled={state === 'pending'}
        onClick={async () => {
          setState('pending');
          const response = await fetch('/api/roadmaps/current/items', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ concept_slugs: slugs }),
          });
          if (!response.ok) {
            setState('error');
            return;
          }
          setState('done');
          router.refresh();
        }}
      >
        {state === 'pending' ? <Loader2 className="animate-spin" /> : <Plus />}
        {label}
      </Button>
      {state === 'error' && (
        <p role="alert" className="text-sm text-destructive">
          Could not add them. Do you have a route yet?{' '}
          <Link href="/explore" className="underline">
            Pick a destination
          </Link>
          .
        </p>
      )}
    </div>
  );
}

function ConceptChip({ concept }: { concept: ConceptRef }) {
  return (
    <Link
      href={`/concepts/${concept.slug}`}
      className="rounded-full border px-2.5 py-1 text-xs transition-colors hover:bg-muted"
    >
      {concept.name}
    </Link>
  );
}

function JobMatchPanel({ match }: { match: JobMatch }) {
  return (
    <div className="space-y-4">
      <p className="text-sm">
        <span className="font-display text-2xl font-semibold">{match.coverage_percent}%</span>{' '}
        <span className="text-muted-foreground">
          of the {match.requirements_found} requirements we could identify are already
          evidenced.
        </span>
      </p>

      {match.matched.length > 0 && (
        <div>
          <p className="eyebrow">Already evidenced</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {match.matched.map((entry) => (
              <ConceptChip key={entry.concept.slug} concept={entry.concept} />
            ))}
          </div>
        </div>
      )}

      {match.missing.length > 0 && (
        <div>
          <p className="eyebrow">Gaps</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {match.missing.map((entry) => (
              <ConceptChip key={entry.concept.slug} concept={entry.concept} />
            ))}
          </div>
          <div className="mt-3">
            <AddToRoute slugs={match.addable_slugs} label="Add these gaps to my route" />
          </div>
        </div>
      )}

      {match.unmatched_terms.length > 0 && (
        <p className="text-sm text-muted-foreground">
          No concept in the catalogue covers: {match.unmatched_terms.join(', ')}. Those are
          not scored either way.
        </p>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------
// the page
// --------------------------------------------------------------------------

export function ResumeWorkspace({
  email,
  status,
  initialProfile,
  initialUploads,
  roles,
}: {
  email: string;
  status: ResumeStatus | null;
  initialProfile: ResumeProfile | null;
  initialUploads: ResumeUpload[];
  roles: RoleOption[];
}) {
  const [tab, setTab] = useState<'build' | 'review'>('build');

  return (
    <div className="space-y-6">
      {status && !status.available && (
        <Notice tone="warn">
          The local model is not running, so the summary paragraph and the bullet
          rewrites are unavailable. Everything else on this page — skills, projects,
          role scores, company matches and the ATS check — is computed and works
          regardless. Start it with <code>ollama serve</code> for the rest.
        </Notice>
      )}

      <div className="flex gap-2 border-b">
        {(
          [
            ['build', 'Build from my progress'],
            ['review', 'Review an existing résumé'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            aria-current={tab === key}
            className={cn(
              '-mb-px border-b-2 px-3 py-2 text-sm transition-colors',
              tab === key
                ? 'border-primary font-medium text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'build' ? (
        <BuildTab email={email} initialProfile={initialProfile} roles={roles} />
      ) : (
        <ReviewTab initialUploads={initialUploads} status={status} roles={roles} />
      )}
    </div>
  );
}

// --------------------------------------------------------------------------
// build
// --------------------------------------------------------------------------

function BuildTab({
  email,
  initialProfile,
  roles,
}: {
  email: string;
  initialProfile: ResumeProfile | null;
  roles: RoleOption[];
}) {
  const [profile, setProfile] = useState<ResumeProfile>(
    initialProfile ?? {
      full_name: null,
      headline: null,
      email: null,
      phone: null,
      location: null,
      links: [],
      summary: null,
    },
  );
  const [saved, setSaved] = useState(false);
  const [role, setRole] = useState('');
  const [jd, setJd] = useState('');
  const [document_, setDocument] = useState<ResumeDocument | null>(null);
  const [busy, setBusy] = useState<'none' | 'build' | 'print'>('none');
  const [error, setError] = useState<string | null>(null);

  const set = (key: keyof ResumeProfile, value: string) =>
    setProfile((prev) => ({ ...prev, [key]: value || null }));

  async function saveProfile() {
    setSaved(false);
    const response = await fetch('/api/resume/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...profile, links: profile.links }),
    });
    if (response.ok) {
      setProfile(await response.json());
      setSaved(true);
    }
  }

  const body = useCallback(
    () =>
      JSON.stringify({
        target_role_slug: role || null,
        job_description: jd.trim() || null,
        polish: true,
      }),
    [role, jd],
  );

  async function build() {
    setBusy('build');
    setError(null);
    const response = await fetch('/api/resume/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body(),
    });
    setBusy('none');
    if (!response.ok) {
      setError('Could not build the résumé.');
      return;
    }
    setDocument(await response.json());
  }

  async function print() {
    // The window has to be opened in the click handler or the popup blocker
    // eats it; the HTML is written into it once it arrives.
    const target = window.open('', '_blank');
    setBusy('print');
    const response = await fetch('/api/resume/render', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body(),
    });
    setBusy('none');
    if (!response.ok) {
      target?.close();
      setError('Could not render the printable version.');
      return;
    }
    const html = await response.text();
    if (!target) {
      setError('Your browser blocked the print window. Allow pop-ups for this site.');
      return;
    }
    target.document.open();
    target.document.write(html);
    target.document.close();
  }

  return (
    <div className="space-y-6">
      <Section
        title="Contact block"
        description="The only part of the résumé you have to type. Everything below it is read from your record."
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="full_name">Full name</Label>
            <Input
              id="full_name"
              value={profile.full_name ?? ''}
              onChange={(e) => set('full_name', e.target.value)}
              placeholder="Jane Doe"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="headline">Headline</Label>
            <Input
              id="headline"
              value={profile.headline ?? ''}
              onChange={(e) => set('headline', e.target.value)}
              placeholder="Backend Developer"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              value={profile.email ?? ''}
              onChange={(e) => set('email', e.target.value)}
              placeholder={email}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="phone">Phone</Label>
            <Input
              id="phone"
              value={profile.phone ?? ''}
              onChange={(e) => set('phone', e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="location">Location</Label>
            <Input
              id="location"
              value={profile.location ?? ''}
              onChange={(e) => set('location', e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="links">Links, one per line</Label>
            <Textarea
              id="links"
              rows={3}
              value={profile.links.join('\n')}
              onChange={(e) =>
                setProfile((prev) => ({
                  ...prev,
                  links: e.target.value.split('\n'),
                }))
              }
              placeholder={'github.com/janedoe\nlinkedin.com/in/janedoe'}
            />
          </div>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <Button size="sm" variant="outline" onClick={saveProfile}>
            Save contact block
          </Button>
          {saved && (
            <span className="flex items-center gap-1.5 text-sm text-success">
              <Check className="h-4 w-4" /> Saved
            </span>
          )}
        </div>
      </Section>

      <Section
        title="Tailor it"
        description="Aim at a role, or paste the job description and see the diff against what you have completed."
      >
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="role">Target role</Label>
            <select
              id="role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring"
            >
              <option value="">Strongest role, computed</option>
              {roles.map((option) => (
                <option key={option.slug} value={option.slug}>
                  {option.title} — {option.percent}% ready
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="jd">Job description (optional)</Label>
            <Textarea
              id="jd"
              rows={7}
              value={jd}
              onChange={(e) => setJd(e.target.value)}
              placeholder="Paste the posting here. We diff it against your completed concepts and show what is missing."
            />
          </div>

          <div className="flex flex-wrap gap-3">
            <Button onClick={build} disabled={busy !== 'none'}>
              {busy === 'build' ? <Loader2 className="animate-spin" /> : <Wand2 />}
              Build my résumé
            </Button>
            <Button variant="outline" onClick={print} disabled={busy !== 'none'}>
              {busy === 'print' ? <Loader2 className="animate-spin" /> : <Printer />}
              Print / save as PDF
            </Button>
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
        </div>
      </Section>

      {document_ && <BuiltResume document={document_} />}
    </div>
  );
}

function BuiltResume({ document }: { document: ResumeDocument }) {
  const hasEvidence =
    document.stats.concepts_completed > 0 || document.stats.projects_shipped > 0;

  return (
    <div className="space-y-6">
      <Section title="Summary">
        <p className="text-sm leading-relaxed">{document.summary}</p>
        <p className="mt-3 text-xs text-muted-foreground">
          {document.summary_is_generated
            ? `Drafted by ${document.generated_by} from your records — check it before you send it.`
            : document.degraded
              ? 'Written from your records without a model, because none was reachable.'
              : 'Written from your records.'}
        </p>

        {!hasEvidence && (
          <div className="mt-4">
            <Notice tone="info">
              There is nothing to put on a résumé yet. Complete a concept or ship a
              project and it will appear here with the date it happened.{' '}
              <Link href="/roadmap" className="underline">
                Your route
              </Link>
            </Notice>
          </div>
        )}
      </Section>

      <div className="grid gap-4 sm:grid-cols-4">
        {(
          [
            ['Concepts', document.stats.concepts_completed],
            ['Projects shipped', document.stats.projects_shipped],
            ['Tracked hours', document.stats.hours_invested],
            ['Badges', document.stats.badges],
          ] as const
        ).map(([label, value]) => (
          <div key={label} className="rounded-lg border bg-card p-4">
            <p className="font-display text-2xl font-semibold">{value}</p>
            <p className="text-xs text-muted-foreground">{label}</p>
          </div>
        ))}
      </div>

      {document.projects.length > 0 && (
        <Section title="Projects" description="Each one has a passing test run behind it.">
          <ul className="space-y-4">
            {document.projects.map((project) => (
              <li key={project.slug}>
                <div className="flex items-baseline justify-between gap-4">
                  <Link href={`/projects/${project.slug}`} className="font-medium hover:underline">
                    {project.title}
                  </Link>
                  <span className="text-xs text-muted-foreground">
                    {project.tests_passed}/{project.tests_total} tests passing
                  </span>
                </div>
                <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-muted-foreground">
                  {project.bullets.map((bullet) => (
                    <li key={bullet}>{bullet}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {document.skills.length > 0 && (
        <Section title="Skills, evidenced">
          <div className="space-y-4">
            {document.skills.map((group) => (
              <div key={group.domain_slug}>
                <p className="eyebrow">{group.domain_name}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {group.concepts.map((concept) => (
                    <ConceptChip key={concept.slug} concept={concept} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {document.gaps.length > 0 && document.target_role && (
        <Section
          title={`Gaps for ${document.target_role.title}`}
          description={`${document.target_role.percent}% ready. Each of these adds the percentage shown.`}
        >
          <ul className="space-y-2 text-sm">
            {document.gaps.map((gap) => (
              <li key={gap.concept.slug} className="flex items-center justify-between gap-4">
                <Link href={`/concepts/${gap.concept.slug}`} className="hover:underline">
                  {gap.concept.name}
                  {/* Several concept names ("Learn the Basics") only mean
                      something next to the domain they belong to. */}
                  <span className="ml-2 text-xs text-muted-foreground">
                    {gap.concept.domain_name}
                  </span>
                </Link>
                <span className="text-xs text-muted-foreground">
                  +{gap.percent_contribution}%{gap.in_roadmap ? ' · already on your route' : ''}
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-4">
            <AddToRoute
              slugs={document.gaps.filter((g) => !g.in_roadmap).map((g) => g.concept.slug)}
            />
          </div>
        </Section>
      )}

      {document.job_match && (
        <Section title="Against that job description">
          <JobMatchPanel match={document.job_match} />
        </Section>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------
// review
// --------------------------------------------------------------------------

const SEVERITY_ORDER: Record<string, string> = {
  high: 'border-destructive/40 text-destructive',
  medium: 'border-amber-500/40',
  low: 'border-border',
};

function ReviewTab({
  initialUploads,
  status,
  roles,
}: {
  initialUploads: ResumeUpload[];
  status: ResumeStatus | null;
  roles: RoleOption[];
}) {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploads, setUploads] = useState(initialUploads);
  const [selected, setSelected] = useState<number | null>(initialUploads[0]?.id ?? null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [busy, setBusy] = useState<'none' | 'upload' | 'analyse'>('none');
  const [error, setError] = useState<string | null>(null);
  const [role, setRole] = useState('');
  const [jd, setJd] = useState('');
  const [showText, setShowText] = useState(false);
  const [rawText, setRawText] = useState('');

  const maxMb = status?.max_upload_mb ?? 2;

  async function onFile(file: File) {
    setError(null);
    if (file.size > maxMb * 1024 * 1024) {
      setError(`That file is ${(file.size / 1024 / 1024).toFixed(1)} MB. The cap is ${maxMb} MB.`);
      return;
    }
    setBusy('upload');

    // Base64 rather than multipart: the BFF proxy reads request bodies as text,
    // which corrupts binary on the way through.
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = '';
    for (let i = 0; i < bytes.length; i += 0x8000) {
      binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    }

    const response = await fetch('/api/resume/uploads/inline', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: file.name,
        content_base64: btoa(binary),
        content_type: file.type || '',
      }),
    });
    setBusy('none');

    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      setError(detail.detail ?? 'That file could not be accepted.');
      return;
    }
    const created: ResumeUpload = await response.json();
    setUploads((prev) => [created, ...prev]);
    setSelected(created.id);
    setAnalysis(null);
    setRawText('');
  }

  async function analyse(refresh = false) {
    if (selected === null) return;
    setBusy('analyse');
    setError(null);
    const response = await fetch(`/api/resume/uploads/${selected}/analyse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_role_slug: role || null,
        job_description: jd.trim() || null,
        refresh,
      }),
    });
    setBusy('none');
    if (!response.ok) {
      setError('The analysis could not be run.');
      return;
    }
    setAnalysis(await response.json());
  }

  async function remove(id: number) {
    await fetch(`/api/resume/uploads/${id}`, { method: 'DELETE' });
    setUploads((prev) => prev.filter((u) => u.id !== id));
    if (selected === id) {
      setSelected(null);
      setAnalysis(null);
    }
    router.refresh();
  }

  async function removeAll() {
    await fetch('/api/resume/uploads', { method: 'DELETE' });
    setUploads([]);
    setSelected(null);
    setAnalysis(null);
    router.refresh();
  }

  async function loadText() {
    if (selected === null) return;
    if (!showText && !rawText) {
      const response = await fetch(`/api/resume/uploads/${selected}/text`);
      setRawText(response.ok ? await response.text() : '');
    }
    setShowText((prev) => !prev);
  }

  const current = uploads.find((u) => u.id === selected) ?? null;

  return (
    <div className="space-y-6">
      <Section
        title="Upload your résumé"
        description={`PDF, DOCX or plain text, up to ${maxMb} MB. It is yours: nobody else can read it, and you can delete it at any time.`}
      >
        <input
          ref={fileInput}
          type="file"
          accept=".pdf,.docx,.txt,.md,application/pdf,text/plain"
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void onFile(file);
            e.target.value = '';
          }}
        />
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => fileInput.current?.click()} disabled={busy === 'upload'}>
            {busy === 'upload' ? <Loader2 className="animate-spin" /> : <Upload />}
            Choose a file
          </Button>
          {uploads.length > 0 && (
            <Button variant="destructive" size="sm" onClick={removeAll}>
              <Trash2 /> Delete everything I have uploaded
            </Button>
          )}
        </div>
        {error && (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {error}
          </p>
        )}

        {uploads.length > 0 && (
          <ul className="mt-5 divide-y rounded-lg border">
            {uploads.map((upload) => (
              <li
                key={upload.id}
                className={cn(
                  'flex items-center gap-3 p-3 text-sm',
                  upload.id === selected && 'bg-muted/40',
                )}
              >
                <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                <button
                  type="button"
                  className="min-w-0 flex-1 truncate text-left hover:underline"
                  onClick={() => {
                    setSelected(upload.id);
                    setAnalysis(null);
                    setRawText('');
                    setShowText(false);
                  }}
                >
                  {upload.filename}
                  <span className="ml-2 text-xs text-muted-foreground">
                    {upload.kind.toUpperCase()} · {Math.round(upload.size_bytes / 1024)} KB
                    {upload.extraction_ok ? '' : ' · no readable text'}
                  </span>
                </button>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Delete ${upload.filename}`}
                  onClick={() => remove(upload.id)}
                >
                  <Trash2 />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {current && (
        <Section title={`Analyse ${current.filename}`}>
          {!current.extraction_ok && current.extraction_note && (
            <div className="mb-4">
              <Notice tone="bad">{current.extraction_note}</Notice>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="review-role">Target role (optional)</Label>
              <select
                id="review-role"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring"
              >
                <option value="">Best fit, computed</option>
                {roles.map((option) => (
                  <option key={option.slug} value={option.slug}>
                    {option.title}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="review-jd">Job description (optional)</Label>
              <Textarea
                id="review-jd"
                rows={5}
                value={jd}
                onChange={(e) => setJd(e.target.value)}
                placeholder="Paste a posting to diff this résumé against it."
              />
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            <Button onClick={() => analyse(false)} disabled={busy === 'analyse'}>
              {busy === 'analyse' ? <Loader2 className="animate-spin" /> : <Sparkles />}
              Analyse
            </Button>
            {analysis && (
              <Button variant="outline" onClick={() => analyse(true)} disabled={busy === 'analyse'}>
                Re-run
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={loadText}>
              {showText ? <EyeOff /> : <Eye />}
              {showText ? 'Hide' : 'Show'} the text a parser sees
            </Button>
          </div>

          {showText && (
            <pre className="mt-4 max-h-80 overflow-auto rounded-lg border bg-muted/30 p-4 text-xs whitespace-pre-wrap">
              {rawText || '(nothing extractable)'}
            </pre>
          )}
        </Section>
      )}

      {analysis && <AnalysisReport analysis={analysis} />}
    </div>
  );
}

function AnalysisReport({ analysis }: { analysis: Analysis }) {
  return (
    <div className="space-y-6">
      {analysis.degraded && analysis.degraded_reason && (
        <Notice tone="warn">{analysis.degraded_reason}</Notice>
      )}

      <Section
        title="What an applicant tracking system sees"
        description="Deliberately naive — this is the floor, and the floor is what most parsers are."
      >
        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            <p className="eyebrow">Reads cleanly</p>
            <ul className="mt-2 space-y-1 text-sm">
              {analysis.ats.can_extract.map((item) => (
                <li key={item} className="flex gap-2">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                  <span>{item}</span>
                </li>
              ))}
              {analysis.ats.can_extract.length === 0 && (
                <li className="text-muted-foreground">Nothing.</li>
              )}
            </ul>
          </div>
          <div>
            <p className="eyebrow">Cannot read</p>
            <ul className="mt-2 space-y-1 text-sm">
              {analysis.ats.cannot_extract.map((item) => (
                <li key={item} className="flex gap-2">
                  <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                  <span>{item}</span>
                </li>
              ))}
              {analysis.ats.cannot_extract.length === 0 && (
                <li className="text-muted-foreground">Nothing important is missing.</li>
              )}
            </ul>
          </div>
        </div>

        {analysis.ats.warnings.length > 0 && (
          <ul className="mt-6 space-y-1 text-sm text-muted-foreground">
            {analysis.ats.warnings.map((warning) => (
              <li key={warning} className="flex gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{warning}</span>
              </li>
            ))}
          </ul>
        )}

        <p className="mt-6 text-xs text-muted-foreground">
          {analysis.ats.word_count} words · {analysis.ats.text_chars} extractable characters
          {analysis.ats.file.pages ? ` · ${analysis.ats.file.pages} pages` : ''}
        </p>
      </Section>

      {analysis.suggestions.length > 0 && (
        <Section title="What to fix">
          <ul className="space-y-3">
            {analysis.suggestions.map((suggestion, index) => (
              <li
                key={`${suggestion.kind}-${index}`}
                className={cn('rounded-lg border p-4', SEVERITY_ORDER[suggestion.severity])}
              >
                <p className="text-sm">{suggestion.message}</p>
                {suggestion.evidence && (
                  <p className="mt-2 border-l-2 pl-3 text-xs text-muted-foreground italic">
                    {suggestion.evidence}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {analysis.rewrites.length > 0 && (
        <Section
          title="Stronger bullets"
          description={`Drafted by ${analysis.generated_by} from your own words. Check every fact before you use one.`}
        >
          <ul className="space-y-4">
            {analysis.rewrites.map((rewrite, index) => (
              <li key={index} className="rounded-lg border p-4">
                <p className="text-xs text-muted-foreground line-through">{rewrite.original}</p>
                <p className="mt-2 text-sm font-medium">{rewrite.rewrite}</p>
                {rewrite.why && (
                  <p className="mt-1 text-xs text-muted-foreground">{rewrite.why}</p>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {analysis.career_options.length > 0 && (
        <Section
          title="Roles this résumé supports"
          description="Scored against the same weighted skill sets the dashboard uses."
        >
          <ul className="space-y-3">
            {analysis.career_options.map((option) => (
              <li key={option.slug}>
                <div className="flex items-baseline justify-between gap-4">
                  <span className="font-medium">{option.title}</span>
                  <span className="text-sm text-muted-foreground">{option.percent}%</span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${option.percent}%` }}
                  />
                </div>
                {option.description && (
                  <p className="mt-1 text-xs text-muted-foreground">{option.description}</p>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {analysis.detected_skills.length > 0 && (
        <Section
          title="What the résumé actually evidences"
          description="Concepts we could find in the text, matched to the graph."
        >
          <div className="flex flex-wrap gap-1.5">
            {analysis.detected_skills.map((entry) => (
              <ConceptChip key={entry.concept.slug} concept={entry.concept} />
            ))}
          </div>
        </Section>
      )}

      {analysis.companies.length > 0 && (
        <Section
          title="Companies hiring for those roles"
          description="From the seeded company profiles, with what those loops actually ask."
        >
          <ul className="space-y-5">
            {analysis.companies.map((company) => (
              <li key={company.company_slug} className="rounded-lg border p-4">
                <div className="flex items-baseline justify-between gap-4">
                  <Link
                    href={`/companies/${company.company_slug}`}
                    className="flex items-center gap-2 font-medium hover:underline"
                  >
                    <Building2 className="h-4 w-4" />
                    {company.company_name}
                  </Link>
                  <span className="text-xs text-muted-foreground">
                    {company.role_title} · {company.level}
                  </span>
                </div>

                {company.focus_areas.length > 0 && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Focus: {company.focus_areas.map((f) => f.label).join(', ')}
                  </p>
                )}

                {company.sample_questions.length > 0 && (
                  <ul className="mt-3 space-y-1.5 text-sm">
                    {company.sample_questions.map((question) => (
                      <li key={question.question}>
                        <span className="text-muted-foreground">[{question.round}]</span>{' '}
                        {question.question}{' '}
                        <a
                          href={question.source_url}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="text-xs text-muted-foreground underline"
                        >
                          {question.source_name}
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {analysis.learn_next.length > 0 && (
        <Section
          title="What to learn next"
          description={
            analysis.target_role
              ? `Highest-impact gaps for ${analysis.target_role.title}.`
              : undefined
          }
        >
          <ul className="space-y-2 text-sm">
            {analysis.learn_next.map((item) => (
              <li key={item.concept.slug} className="flex items-center justify-between gap-4">
                <Link href={`/concepts/${item.concept.slug}`} className="hover:underline">
                  {item.concept.name}
                  <span className="ml-2 text-xs text-muted-foreground">
                    {item.concept.domain_name}
                  </span>
                </Link>
                <span className="text-xs text-muted-foreground">
                  +{item.percent_contribution}%
                  {item.in_roadmap ? ' · already on your route' : ''}
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-4">
            <AddToRoute
              slugs={analysis.learn_next
                .filter((item) => !item.in_roadmap)
                .map((item) => item.concept.slug)}
            />
          </div>
        </Section>
      )}

      {analysis.job_match && (
        <Section title="Against that job description">
          <JobMatchPanel match={analysis.job_match} />
        </Section>
      )}
    </div>
  );
}
