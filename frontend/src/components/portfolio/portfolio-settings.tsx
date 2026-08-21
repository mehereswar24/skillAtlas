'use client';

/**
 * The owner's side of the portfolio.
 *
 * The design goal is that nobody is ever surprised by what is public. Three
 * things do that work:
 *
 * - A permanent status banner at the top, worded as a state ("Private" /
 *   "Live"), not as a control.
 * - `public_summary` from the API, rendered verbatim: the server's own account
 *   of what a stranger sees, so the answer can never drift from the six
 *   switches that produce it.
 * - Publishing is a separate, deliberate button. Saving details never
 *   publishes, and unpublishing takes effect on the next request.
 *
 * All calls go through the same-origin BFF proxy (`/api/portfolio/…`), so the
 * access token stays in an HttpOnly cookie this code cannot read.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Check,
  Eye,
  EyeOff,
  ExternalLink,
  Globe,
  Loader2,
  Lock,
  Trash2,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

import type { HandleCheck, PortfolioSettings, PortfolioVisibility } from './types';

const VISIBILITY_FIELDS: {
  key: keyof PortfolioVisibility;
  label: string;
  hint: string;
}[] = [
  {
    key: 'show_projects',
    label: 'Projects you have shipped',
    hint: 'Title, brief and test results for each project you passed.',
  },
  {
    key: 'show_project_code',
    label: 'The code you wrote, runnable in the page',
    hint: 'Publishes your submitted files so a visitor can press Run. Off by default.',
  },
  {
    key: 'show_concepts',
    label: 'Concepts you have completed',
    hint: 'Grouped by track. Nothing in progress is ever shown.',
  },
  {
    key: 'show_points',
    label: 'Points and level',
    hint: '',
  },
  {
    key: 'show_badges',
    label: 'Badges',
    hint: '',
  },
  {
    key: 'show_readiness',
    label: 'Role readiness',
    hint: 'Your strongest three roles, as a percentage.',
  },
];

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/portfolio${path}`, {
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    ...init,
  });
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg ?? '').join('; ')
          : 'Something went wrong.',
    );
  }
  return body as T;
}

export function PortfolioSettingsForm({ initial }: { initial: PortfolioSettings }) {
  const [settings, setSettings] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const apply = useCallback(async (label: string, run: () => Promise<PortfolioSettings>) => {
    setBusy(label);
    setError(null);
    try {
      setSettings(await run());
      setSavedAt(Date.now());
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Something went wrong.');
    } finally {
      setBusy(null);
    }
  }, []);

  if (!settings.exists) {
    return <ClaimHandle onCreated={setSettings} />;
  }

  return (
    <div className="space-y-8">
      <StatusBanner settings={settings} />

      {error && (
        <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <Details settings={settings} apply={apply} busy={busy} savedAt={savedAt} />

      <Visibility settings={settings} apply={apply} busy={busy} />

      <Projects settings={settings} apply={apply} busy={busy} />

      <PublishControls settings={settings} apply={apply} busy={busy} />
    </div>
  );
}

// --------------------------------------------------------------------------

function StatusBanner({ settings }: { settings: PortfolioSettings }) {
  const live = settings.is_published;
  return (
    <section
      className={cn(
        'rounded-xl border p-5',
        live ? 'border-success/40 bg-success/5' : 'border-border bg-muted/40',
      )}
    >
      <div className="flex flex-wrap items-start gap-3">
        {live ? (
          <Globe className="mt-0.5 h-5 w-5 shrink-0 text-success" />
        ) : (
          <Lock className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
        )}
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-lg font-semibold">
            {live ? 'Live on the internet' : 'Private'}
          </h2>
          {live && settings.public_url && (
            <Link
              href={settings.public_url}
              className="mt-1 inline-flex items-center gap-1.5 font-mono text-sm text-primary hover:underline"
            >
              {settings.public_url}
              <ExternalLink className="h-3 w-3" />
            </Link>
          )}
          {!live && settings.public_url && (
            <p className="mt-1 text-sm text-muted-foreground">
              Reserved at <code className="font-mono">{settings.public_url}</code> —{' '}
              <Link href={settings.public_url} className="text-primary hover:underline">
                preview it
              </Link>
              . Anyone else opening that link gets “not found”.
            </p>
          )}

          <h3 className="mt-4 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            What a stranger can see
          </h3>
          <ul className="mt-1.5 space-y-1 text-sm">
            {settings.public_summary.map((line) => (
              <li key={line} className="flex items-start gap-2">
                <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-muted-foreground" aria-hidden />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

// --------------------------------------------------------------------------

function ClaimHandle({ onCreated }: { onCreated: (next: PortfolioSettings) => void }) {
  const router = useRouter();
  const [handle, setHandle] = useState('');
  // Stored with the handle it answered, so a reply that arrives after the
  // field has moved on is simply not rendered — no second setState needed to
  // clear it, which is also what keeps this effect free of a synchronous
  // state update in its body.
  const [check, setCheck] = useState<{ forHandle: string; result: HandleCheck } | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const latest = useRef(0);

  // Debounced availability check. Purely advisory — the write path enforces
  // the same rules, so a stale answer cannot let a bad handle through.
  useEffect(() => {
    const candidate = handle.trim();
    if (candidate.length < 3) return;

    const token = ++latest.current;
    const timer = setTimeout(async () => {
      try {
        const result = await call<HandleCheck>(
          `/handle-check?handle=${encodeURIComponent(candidate)}`,
        );
        if (token === latest.current) setCheck({ forHandle: candidate, result });
      } catch {
        // A failed availability check is advisory only — the write path
        // enforces the same rules, so there is nothing to report here.
      }
    }, 350);
    return () => clearTimeout(timer);
  }, [handle]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onCreated(
        await call<PortfolioSettings>('/me', {
          method: 'PUT',
          body: JSON.stringify({ handle: handle.trim() }),
        }),
      );
      router.refresh();
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Could not create it.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={create} className="max-w-lg rounded-xl border bg-card p-6">
      <h2 className="font-display text-xl font-semibold">Choose a handle</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        It becomes your address. Nothing is published until you say so — creating a
        portfolio only reserves the name.
      </p>

      <div className="mt-5">
        <Label htmlFor="handle">Handle</Label>
        <div className="mt-1.5 flex items-center gap-2">
          <span className="font-mono text-sm text-muted-foreground">/u/</span>
          <Input
            id="handle"
            value={handle}
            onChange={(event) => setHandle(event.target.value)}
            placeholder="ada-lovelace"
            autoComplete="off"
            spellCheck={false}
            maxLength={30}
          />
        </div>
        <p className="mt-1.5 text-xs text-muted-foreground">
          3–30 characters: letters, numbers, dashes and underscores.
        </p>
        {check?.forHandle === handle.trim() && (
          <p
            className={cn(
              'mt-1.5 text-xs',
              check.result.available ? 'text-success' : 'text-destructive',
            )}
          >
            {check.result.available
              ? `${check.result.handle} is free.`
              : check.result.reason}
          </p>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {error}
        </p>
      )}

      <Button type="submit" className="mt-5" disabled={busy || handle.trim().length < 3}>
        {busy && <Loader2 className="animate-spin" />}
        Reserve it
      </Button>
    </form>
  );
}

// --------------------------------------------------------------------------

type Apply = (label: string, run: () => Promise<PortfolioSettings>) => Promise<void>;

function Details({
  settings,
  apply,
  busy,
  savedAt,
}: {
  settings: PortfolioSettings;
  apply: Apply;
  busy: string | null;
  savedAt: number | null;
}) {
  const [draft, setDraft] = useState({
    handle: settings.handle ?? '',
    display_name: settings.display_name,
    headline: settings.headline,
    bio: settings.bio,
    location: settings.location,
    github_url: settings.github_url ?? '',
    linkedin_url: settings.linkedin_url ?? '',
    website_url: settings.website_url ?? '',
  });

  function field<K extends keyof typeof draft>(key: K) {
    return {
      value: draft[key],
      onChange: (event: { target: { value: string } }) =>
        setDraft((prev) => ({ ...prev, [key]: event.target.value })),
    };
  }

  return (
    <form
      className="rounded-xl border bg-card p-6"
      onSubmit={(event) => {
        event.preventDefault();
        void apply('details', () =>
          call<PortfolioSettings>('/me', {
            method: 'PUT',
            body: JSON.stringify({
              ...draft,
              github_url: draft.github_url.trim() || null,
              linkedin_url: draft.linkedin_url.trim() || null,
              website_url: draft.website_url.trim() || null,
            }),
          }),
        );
      }}
    >
      <h2 className="font-display text-xl font-semibold">Details</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Only what you type here. Your email address is never published, on any setting.
      </p>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="handle">Handle</Label>
          <Input id="handle" className="mt-1.5" maxLength={30} {...field('handle')} />
        </div>
        <div>
          <Label htmlFor="display_name">Display name</Label>
          <Input
            id="display_name"
            className="mt-1.5"
            maxLength={120}
            placeholder="Ada Lovelace"
            {...field('display_name')}
          />
        </div>
        <div className="sm:col-span-2">
          <Label htmlFor="headline">Headline</Label>
          <Input
            id="headline"
            className="mt-1.5"
            maxLength={200}
            placeholder="Backend engineer, four projects deep"
            {...field('headline')}
          />
        </div>
        <div className="sm:col-span-2">
          <Label htmlFor="bio">About</Label>
          <Textarea id="bio" className="mt-1.5" maxLength={4000} rows={4} {...field('bio')} />
        </div>
        <div>
          <Label htmlFor="location">Location</Label>
          <Input id="location" className="mt-1.5" maxLength={120} {...field('location')} />
        </div>
        <div>
          <Label htmlFor="github_url">GitHub</Label>
          <Input
            id="github_url"
            className="mt-1.5"
            placeholder="https://github.com/…"
            {...field('github_url')}
          />
        </div>
        <div>
          <Label htmlFor="linkedin_url">LinkedIn</Label>
          <Input
            id="linkedin_url"
            className="mt-1.5"
            placeholder="https://linkedin.com/in/…"
            {...field('linkedin_url')}
          />
        </div>
        <div>
          <Label htmlFor="website_url">Website</Label>
          <Input
            id="website_url"
            className="mt-1.5"
            placeholder="https://…"
            {...field('website_url')}
          />
        </div>
      </div>

      <div className="mt-5 flex items-center gap-3">
        <Button type="submit" disabled={busy !== null}>
          {busy === 'details' && <Loader2 className="animate-spin" />}
          Save details
        </Button>
        {savedAt !== null && busy === null && (
          <span className="flex items-center gap-1.5 text-sm text-success">
            <Check className="h-4 w-4" />
            Saved
          </span>
        )}
        <span className="text-xs text-muted-foreground">Saving does not publish.</span>
      </div>
    </form>
  );
}

// --------------------------------------------------------------------------

function Visibility({
  settings,
  apply,
  busy,
}: {
  settings: PortfolioSettings;
  apply: Apply;
  busy: string | null;
}) {
  return (
    <section className="rounded-xl border bg-card p-6">
      <h2 className="font-display text-xl font-semibold">What appears</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Each of these is a separate decision, and each takes effect immediately.
      </p>

      <ul className="mt-4 divide-y">
        {VISIBILITY_FIELDS.map(({ key, label, hint }) => {
          const on = settings.visibility[key];
          return (
            <li key={key} className="flex items-start gap-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{label}</p>
                {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
              </div>
              <Button
                type="button"
                size="sm"
                variant={on ? 'secondary' : 'outline'}
                disabled={busy !== null}
                aria-pressed={on}
                onClick={() =>
                  apply(key, () =>
                    call<PortfolioSettings>('/me', {
                      method: 'PUT',
                      body: JSON.stringify({ [key]: !on }),
                    }),
                  )
                }
              >
                {on ? <Eye /> : <EyeOff />}
                {on ? 'Shown' : 'Hidden'}
              </Button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

// --------------------------------------------------------------------------

function Projects({
  settings,
  apply,
  busy,
}: {
  settings: PortfolioSettings;
  apply: Apply;
  busy: string | null;
}) {
  return (
    <section className="rounded-xl border bg-card p-6">
      <h2 className="font-display text-xl font-semibold">Your shipped projects</h2>
      {settings.projects.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">
          Nothing yet — only projects whose tests you passed can appear.{' '}
          <Link href="/projects" className="text-primary hover:underline">
            Go build one
          </Link>
          .
        </p>
      ) : (
        <>
          <p className="mt-1 text-sm text-muted-foreground">
            Hide any of them, or add a line about what you were going for.
          </p>
          <ul className="mt-4 divide-y">
            {settings.projects.map((project) => (
              <li key={project.project_id} className="py-4">
                <div className="flex flex-wrap items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <p
                      className={cn(
                        'text-sm font-medium',
                        !project.is_visible && 'text-muted-foreground line-through',
                      )}
                    >
                      {project.title}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {project.concept_name} · {project.runtime}
                    </p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant={project.is_visible ? 'secondary' : 'outline'}
                    disabled={busy !== null}
                    aria-pressed={project.is_visible}
                    onClick={() =>
                      apply(`project-${project.project_id}`, () =>
                        call<PortfolioSettings>(`/me/projects/${project.project_id}`, {
                          method: 'PATCH',
                          body: JSON.stringify({ is_visible: !project.is_visible }),
                        }),
                      )
                    }
                  >
                    {project.is_visible ? <Eye /> : <EyeOff />}
                    {project.is_visible ? 'Shown' : 'Hidden'}
                  </Button>
                </div>

                <ProjectNote project={project} apply={apply} busy={busy} />
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function ProjectNote({
  project,
  apply,
  busy,
}: {
  project: PortfolioSettings['projects'][number];
  apply: Apply;
  busy: string | null;
}) {
  const [note, setNote] = useState(project.note);
  const dirty = note.trim() !== project.note.trim();

  return (
    <div className="mt-2 flex flex-wrap items-end gap-2">
      <div className="min-w-0 flex-1">
        <Label htmlFor={`note-${project.project_id}`} className="text-xs text-muted-foreground">
          Your note (replaces the stock tagline)
        </Label>
        <Input
          id={`note-${project.project_id}`}
          className="mt-1"
          maxLength={1000}
          value={note}
          placeholder={project.tagline}
          onChange={(event) => setNote(event.target.value)}
        />
      </div>
      {dirty && (
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={busy !== null}
          onClick={() =>
            apply(`note-${project.project_id}`, () =>
              call<PortfolioSettings>(`/me/projects/${project.project_id}`, {
                method: 'PATCH',
                body: JSON.stringify({ note }),
              }),
            )
          }
        >
          Save note
        </Button>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------

function PublishControls({
  settings,
  apply,
  busy,
}: {
  settings: PortfolioSettings;
  apply: Apply;
  busy: string | null;
}) {
  const router = useRouter();
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  return (
    <section className="rounded-xl border bg-card p-6">
      <h2 className="font-display text-xl font-semibold">
        {settings.is_published ? 'Take it down' : 'Publish'}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        {settings.is_published
          ? 'Unpublishing is immediate: the URL returns “not found” on the very next request. You can put it back up whenever you like.'
          : 'Publishing makes the page readable by anyone with the link, including search engines. Nothing above is public until you press this.'}
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button
          type="button"
          variant={settings.is_published ? 'outline' : 'default'}
          disabled={busy !== null}
          onClick={() =>
            apply('publish', async () => {
              const next = await call<PortfolioSettings>(
                settings.is_published ? '/me/unpublish' : '/me/publish',
                { method: 'POST' },
              );
              router.refresh();
              return next;
            })
          }
        >
          {busy === 'publish' && <Loader2 className="animate-spin" />}
          {settings.is_published ? 'Unpublish' : 'Publish my portfolio'}
        </Button>

        {confirmingDelete ? (
          <>
            <Button
              type="button"
              variant="destructive"
              disabled={busy !== null}
              onClick={async () => {
                await call<void>('/me', { method: 'DELETE' });
                router.refresh();
              }}
            >
              <Trash2 />
              Yes, delete it
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setConfirmingDelete(false)}
            >
              Cancel
            </Button>
          </>
        ) : (
          <Button
            type="button"
            variant="ghost"
            disabled={busy !== null}
            onClick={() => setConfirmingDelete(true)}
          >
            <Trash2 />
            Delete portfolio
          </Button>
        )}
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        Deleting removes the page and frees the handle. Your progress, points and
        projects are untouched.
      </p>
    </section>
  );
}
